"""
``ibek.manifest.yaml`` — a pattern's declaration of what it vendors, and where.

A pattern folder may carry a manifest describing which of its files are copied
into a destination and where they land. This is the *source* side of vendoring
and is only ever read at fetch time; the destination side (``runtime-lock.yaml``)
is deliberately offline and never needs the manifest, so ``ibek pattern check``
does not import this module.

The manifest is an ordered, first-match-wins **allow-list**: a file matched by no
entry is not vendored. A pattern with no manifest is vendored through the
synthesised :data:`DEFAULT_MANIFEST_YAML`, which reproduces the historical
"everything into ``config/``" behaviour — one vendoring path, no branches.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ibek.globals import BaseSettings

from .sources import PatternError

# The manifest is looked for at the pattern folder root, and is never vendored.
MANIFEST_NAME = "ibek.manifest.yaml"

# ``version:`` exists so the format can evolve. An unknown version is a hard
# error rather than a best-effort read, because a manifest is an allow-list and
# a misread one silently omits files from the destination.
SUPPORTED_MANIFEST_VERSIONS = frozenset({1})

# ``schema.py`` merges ``config/*.ibek.support.yaml`` non-recursively when it
# builds an instance's editor schema, so a support yaml vendored anywhere else
# vendors cleanly, checks cleanly, and is then silently missing from the schema.
# (``ibek runtime generate2`` globs ``config/**/*.ibek.support.yaml`` and *does*
# find a nested one, so the IOC still boots — what is lost is editor validation.)
SUPPORT_YAML_SUFFIX = ".ibek.support.yaml"
SUPPORT_YAML_DIR = "config"

# A pattern with no manifest is parsed, validated and compiled from *this*
# string, so "no manifest" is not a second code path: every consumer only ever
# sees a validated PatternManifest.
DEFAULT_MANIFEST_YAML = """\
version: 1
vendor:
  - src: '.*'
    dest: config
"""

# ``\\1``-style and ``\\g<...>`` backreferences mark a ``dest`` as a substitution
# template (which produces the whole destination path) rather than a plain folder.
_SUBSTITUTION_RE = re.compile(r"\\(?:\d|g<)")


class ManifestError(PatternError):
    """An invalid ``ibek.manifest.yaml``, or a destination it cannot produce.

    Subclasses ``PatternError`` so the CLI reports it as a user-facing error
    (message + exit 1) with no traceback.
    """


class VendorRule(BaseSettings):
    """One ``vendor:`` entry: which files it claims, and where they land."""

    src: str
    dest: str


class PatternManifest(BaseSettings):
    """A parsed, validated ``ibek.manifest.yaml``."""

    version: int
    vendor: list[VendorRule]


def is_substitution(dest: str) -> bool:
    """True if ``dest`` is a substitution template rather than a plain folder."""
    return _SUBSTITUTION_RE.search(dest) is not None


def _entry_prefix(index: int, rule: VendorRule) -> str:
    """Name the offending entry, so no failure is anonymous."""
    return f"{MANIFEST_NAME} entry {index} (src={rule.src!r}, dest={rule.dest!r}): "


def _validate_version(raw: dict) -> None:
    """Check ``version:`` on the *raw* mapping, before the model is validated.

    Order matters: the model forbids unknown keys, so a manifest written for a
    future ibek (which will carry future keys) would otherwise be reported as
    "extra inputs are not permitted" and never mention the version at all —
    telling the reader their manifest is illegal rather than their ibek is old.
    """
    version = raw.get("version")
    if version not in SUPPORTED_MANIFEST_VERSIONS:
        supported = ", ".join(str(v) for v in sorted(SUPPORTED_MANIFEST_VERSIONS))
        raise ManifestError(
            f"{MANIFEST_NAME}: manifest version {version!r} is not supported by "
            f"this ibek (supported: {supported}); upgrade ibek to read it"
        )


def _validate_manifest(manifest: PatternManifest) -> None:
    """Validate the whole manifest, aborting on the first bad entry.

    A skipped-with-warning entry would mean a file that should be in the
    destination silently is not, which is not acceptable in an integrity system.
    """
    if not manifest.vendor:
        raise ManifestError(f"{MANIFEST_NAME}: 'vendor' must list at least one entry")
    for index, rule in enumerate(manifest.vendor):
        prefix = _entry_prefix(index, rule)
        try:
            re.compile(rule.src)
        except re.error as exc:
            raise ManifestError(f"{prefix}invalid src regex: {exc}") from exc
        if PurePosixPath(rule.dest).is_absolute():
            raise ManifestError(
                f"{prefix}dest must be relative to the destination root"
            )
        if not is_substitution(rule.dest) and ".." in PurePosixPath(rule.dest).parts:
            raise ManifestError(f"{prefix}dest must not contain '..'")


def _symlink_message(pattern_name: str, rel: str) -> str:
    return (
        f"{pattern_name}: {rel!r} is a symlink; symlinks in a pattern folder are "
        "refused - not followed, not vendored, not hashed"
    )


def load_manifest(pattern_dir: Path) -> PatternManifest:
    """Load and validate ``pattern_dir``'s manifest, or synthesise the default.

    The manifest is a file in the pattern folder like any other, so the symlink
    refusal applies to it too — and applies *here* rather than only in
    :func:`plan_vendor`, because this is where it is opened. Reading it first
    would make it the one file in a pattern folder that is followed, and would
    surface a link to a directory (or to an unreadable file) as a raw traceback
    rather than as a ``ManifestError``.
    """
    path = pattern_dir / MANIFEST_NAME
    if path.is_symlink():
        raise ManifestError(_symlink_message(pattern_dir.name, MANIFEST_NAME))
    if path.is_file():
        try:
            text = path.read_text()
        except OSError as exc:
            raise ManifestError(f"{MANIFEST_NAME}: cannot be read: {exc}") from exc
    else:
        text = DEFAULT_MANIFEST_YAML
    try:
        raw = YAML(typ="safe").load(text) or {}
    except YAMLError as exc:
        raise ManifestError(f"{MANIFEST_NAME}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestError(f"{MANIFEST_NAME}: expected a mapping at the top level")
    _validate_version(raw)
    try:
        manifest = PatternManifest.model_validate(raw)
    except ValidationError as exc:
        raise ManifestError(f"{MANIFEST_NAME}: {exc}") from exc
    _validate_manifest(manifest)
    return manifest


def _validate_key(prefix: str, rel: str, key: str) -> str:
    """Validate a produced destination key, after any substitution.

    Returns the key in normal form. Two spellings of one destination
    (``config/x`` and ``config/./x``) must compare equal, or the collision check
    below waves them through and they silently overwrite each other on disk while
    the lock records two different hashes for the one surviving file.
    """
    if not key:
        raise ManifestError(f"{prefix}{rel} produced an empty destination path")
    dest = PurePosixPath(key)
    key = dest.as_posix()
    if key == ".":
        raise ManifestError(f"{prefix}{rel} produced an empty destination path")
    if dest.is_absolute():
        raise ManifestError(
            f"{prefix}{rel} -> {key!r} must be relative to the destination root"
        )
    if ".." in dest.parts:
        raise ManifestError(f"{prefix}{rel} -> {key!r} must not contain '..'")
    if dest.name.endswith(SUPPORT_YAML_SUFFIX) and dest.parent != PurePosixPath(
        SUPPORT_YAML_DIR
    ):
        raise ManifestError(
            f"{prefix}{rel} -> {key!r}: a vendored *{SUPPORT_YAML_SUFFIX} must land "
            f"at the {SUPPORT_YAML_DIR}/ root; `ibek pattern schema` merges "
            f"{SUPPORT_YAML_DIR}/*{SUPPORT_YAML_SUFFIX} non-recursively, so a "
            "misrouted one vendors cleanly, checks cleanly, and is then silently "
            "missing from the instance's schema"
        )
    return key


def _destination(index: int, rule: VendorRule, match: re.Match, rel: str) -> str:
    """Resolve the destination-root-relative key one rule produces for ``rel``."""
    prefix = _entry_prefix(index, rule)
    if is_substitution(rule.dest):
        try:
            key = match.expand(rule.dest)
        except (re.error, IndexError) as exc:
            raise ManifestError(
                f"{prefix}{rel}: invalid dest substitution: {exc}"
            ) from exc
    else:
        key = (PurePosixPath(rule.dest) / rel).as_posix()
    return _validate_key(prefix, rel, key)


def _pattern_files(pattern_dir: Path) -> list[tuple[Path, str]]:
    """Every vendorable file in the pattern folder, as (path, relative posix).

    Walked before the manifest is read, so a symlink is refused rather than
    resolved no matter where in the folder it sits — including the manifest
    itself, and including a folder no rule matches, so one cannot be smuggled
    past the check by excluding it.
    """
    if pattern_dir.is_symlink():
        # ``rglob`` never yields the folder itself, and a symlinked pattern
        # folder makes every file beneath it come from somewhere else entirely.
        raise ManifestError(_symlink_message(pattern_dir.name, "."))
    files: list[tuple[Path, str]] = []
    for path in sorted(pattern_dir.rglob("*")):
        rel = path.relative_to(pattern_dir).as_posix()
        # Checked before is_file(), which follows symlinks (and silently skips
        # broken ones).
        if path.is_symlink():
            raise ManifestError(_symlink_message(pattern_dir.name, rel))
        if rel == MANIFEST_NAME or not path.is_file():
            continue
        files.append((path, rel))
    return files


def _refuse_nested_keys(plan: dict[str, Path], pattern_dir: Path) -> None:
    """Refuse a plan in which one destination is a parent folder of another.

    ``config/a`` cannot be both a file and the folder holding ``config/a/b``.
    Left to the write, the second one fails ``mkdir`` with a raw
    ``FileExistsError`` after the first has already been written.
    """
    for key in sorted(plan):
        for parent in PurePosixPath(key).parents:
            other = plan.get(parent.as_posix())
            if other is None:
                continue
            source = plan[key].relative_to(pattern_dir).as_posix()
            raise ManifestError(
                f"{MANIFEST_NAME}: {source} vendors to {key!r} but "
                f"{other.relative_to(pattern_dir).as_posix()} vendors to "
                f"{parent.as_posix()!r}; one destination cannot be both a file "
                "and a folder"
            )


def plan_vendor(pattern_dir: Path) -> list[tuple[Path, str]]:
    """Return the complete ``(source path, destination key)`` plan, or raise.

    Every source path is absolute; every destination key is relative to the
    destination root (``config/...`` for a pattern with no manifest). The plan is
    fully validated before it is returned, so ``_vendor_files`` cannot leave a
    half-vendored tree behind: nothing is written until this has succeeded.
    """
    files = _pattern_files(pattern_dir)
    manifest = load_manifest(pattern_dir)
    # Compile up front so a bad regex fails before any destination is resolved.
    rules = [(re.compile(rule.src), rule) for rule in manifest.vendor]

    plan: dict[str, Path] = {}
    for path, rel in files:
        for index, (regex, rule) in enumerate(rules):
            match = regex.fullmatch(rel)
            if match is None:
                continue
            key = _destination(index, rule, match, rel)
            if key in plan:
                first = plan[key].relative_to(pattern_dir).as_posix()
                raise ManifestError(
                    f"{_entry_prefix(index, rule)}{rel} and {first} both vendor to "
                    f"{key!r}; one would silently overwrite the other"
                )
            plan[key] = path
            break
    if not plan:
        # The same mistake as ``vendor: []``, one character further on. Left
        # silent it is worse than that: `update` onto a manifest that matches
        # nothing prunes every file the pattern had, records ``files: {}``, and
        # `check` then passes having verified nothing.
        raise ManifestError(
            f"{pattern_dir.name}: no file is matched by any {MANIFEST_NAME} entry, "
            "so nothing would be vendored - a pattern that vendors nothing is a "
            "mistake, not a policy"
        )
    _refuse_nested_keys(plan, pattern_dir)
    # Sorted by destination key so the lock's file ordering is deterministic
    # even under substitutions that reorder relative to the source walk.
    return [(source, key) for key, source in sorted(plan.items())]
