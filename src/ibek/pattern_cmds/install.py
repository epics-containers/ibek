"""
``ibek pattern install`` — install runtime patterns into a generic IOC image.

``ibek pattern add`` vendors a pattern into one IOC instance. ``install`` runs at
image build time and puts a pattern's files where the image's compiled support
modules put theirs, so every instance of the image can use the pattern's
entities, and the image's ``ibek.ioc.schema.json`` includes them:

- ``*.ibek.support.yaml`` to ``IBEK_DEFS``
- ``*.pvi.device.yaml`` to ``PVI_DEFS``
- ``*.proto`` and ``*.protocol`` to ``SUPPORT_PROTOCOL``
- ``*.template``, ``*.db`` and ``*.req`` to ``SUPPORT/<library>/db``, which is
  on msi's ``SUPPORT/*/db`` include path and in autosave's req file search

The pattern's ``ibek.manifest.yaml`` selects the files, exactly as for ``add``;
only their destinations differ, chosen by file name rather than by the manifest's
``dest``.

Every destination of every pattern in one run is planned, and every refusal
checked, before a file is written: a run either installs the whole list or
writes nothing. What a run installs is recorded in the image lock
(``GLOBALS.IMAGE_PATTERN_LOCK``), which ``ibek pattern check --image`` verifies.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ibek.globals import GLOBALS, BaseSettings
from ibek.support import support_yaml_module

from .lock import file_hash
from .manifest import SUPPORT_YAML_SUFFIX, plan_vendor
from .sources import (
    PatternError,
    PatternRef,
    clone_library,
    cloned_pattern,
    fetch_pattern,
    is_local,
    library_commit,
    library_registry,
    parse_ref,
    source_label,
)
from .vendor import CheckResult

IMAGE_LOCK_VERSION = 1
IMAGE_LOCK_KEYS = ("version", "patterns")

PVI_SUFFIX = ".pvi.device.yaml"
PROTOCOL_SUFFIXES = (".proto", ".protocol")
DATABASE_SUFFIXES = (".template", ".db")
REQ_SUFFIX = ".req"


class InstalledPattern(BaseSettings):
    """One installed pattern's image lock record.

    ``files`` keys are paths relative to ``EPICS_ROOT``. ``commit`` is the
    library commit for a git source, and None for a local folder, which has no
    pinned commit.
    """

    library: str
    version: str
    source: str
    commit: str | None = None
    modules: list[str]
    files: dict[str, str]


class ImageLock:
    """Read/modify/write the image's pattern lock."""

    def __init__(self, path: Path):
        self.path = path
        self.patterns: dict[str, InstalledPattern] = {}
        if path.exists():
            self.load()

    def load(self) -> None:
        try:
            raw = YAML(typ="safe").load(self.path) or {}
        except YAMLError as exc:
            raise PatternError(f"{self.path}: invalid YAML: {exc}") from exc
        if not isinstance(raw, dict):
            raise PatternError(f"{self.path}: expected a mapping at the top level")
        if not raw:
            return
        version = raw.get("version")
        if version != IMAGE_LOCK_VERSION:
            raise PatternError(
                f"{self.path}: unsupported image lock version {version!r} "
                f"(this ibek reads: {IMAGE_LOCK_VERSION})"
            )
        unknown = sorted(str(key) for key in raw if key not in IMAGE_LOCK_KEYS)
        if unknown:
            raise PatternError(
                f"{self.path}: unknown top-level key(s) {', '.join(unknown)} "
                f"(an image lock holds only {', '.join(IMAGE_LOCK_KEYS)})"
            )
        patterns = raw.get("patterns") or {}
        if not isinstance(patterns, dict):
            raise PatternError(f"{self.path}: 'patterns' must be a mapping")
        try:
            self.patterns = {
                str(name): InstalledPattern(**entry) for name, entry in patterns.items()
            }
        except (TypeError, ValidationError) as exc:
            raise PatternError(f"{self.path}: invalid pattern entry: {exc}") from exc
        for name, entry in self.patterns.items():
            for key in entry.files:
                if _escapes(key):
                    raise PatternError(
                        f"{self.path}: pattern {name!r} file {key!r} is not a "
                        "path inside EPICS_ROOT"
                    )

    def save(self) -> None:
        data = {
            "version": IMAGE_LOCK_VERSION,
            "patterns": {
                name: {
                    "library": entry.library,
                    "version": entry.version,
                    "source": entry.source,
                    "commit": entry.commit,
                    "modules": list(entry.modules),
                    "files": dict(sorted(entry.files.items())),
                }
                for name, entry in sorted(self.patterns.items())
            },
        }
        yaml = YAML()
        yaml.default_flow_style = False
        yaml.width = 4096
        stream = StringIO()
        yaml.dump(data, stream)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(stream.getvalue())


def _escapes(key: str) -> bool:
    path = Path(key)
    return path.is_absolute() or ".." in path.parts


@dataclass
class _Fetched:
    """A pattern fetched for installing."""

    ref: PatternRef
    library: str
    pattern_dir: Path
    source: str
    commit: str | None


@dataclass
class _Placement:
    """One file to install: where it comes from and where it goes."""

    pattern: str
    source: Path
    target: Path


def read_list_file(path: Path) -> list[str]:
    """Pattern references from a list file: one per line, ``#`` comments."""
    refs = []
    for line in path.read_text().splitlines():
        text = line.partition("#")[0].strip()
        if text:
            refs.append(text)
    return refs


def parse_install_refs(refs: list[str]) -> list[PatternRef]:
    """Parse references, each of which must name its library and version.

    An image is built from pins: the library names the support folder its
    database files go in, and a version-less reference would install whatever
    the library's default branch holds at build time.
    """
    if not refs:
        raise PatternError("no patterns to install")
    parsed: list[PatternRef] = []
    seen: set[str] = set()
    for text in refs:
        ref = parse_ref(text)
        if not ref.library or not ref.version:
            raise PatternError(
                f"{text!r}: install needs library:pattern@version, "
                "e.g. ibek-runtime-streamdevice:lakeshore340@1.0.0"
            )
        if ref.name in seen:
            raise PatternError(f"pattern {ref.name!r} is listed more than once")
        seen.add(ref.name)
        parsed.append(ref)
    return parsed


def _fetch_all(
    refs: list[PatternRef],
    source_override: str | None,
    extra_libraries: dict[str, str] | None,
    tmp: Path,
) -> list[_Fetched]:
    """Fetch every pattern, cloning each library at each version only once."""
    registry = library_registry(extra_libraries)
    clones: dict[tuple[str, str], tuple[Path, str]] = {}
    fetched: list[_Fetched] = []
    for index, ref in enumerate(refs):
        assert ref.library and ref.version  # parse_install_refs guarantees both
        if source_override:
            uri = source_override
        elif ref.library in registry:
            uri = registry[ref.library]
        else:
            raise PatternError(
                f"unknown library {ref.library!r}; "
                f"known: {', '.join(sorted(registry)) or '(none)'}"
            )
        commit: str | None = None
        if is_local(uri):
            pattern_dir = fetch_pattern(
                uri, ref.name, ref.version, _new_dir(tmp / f"local-{index}")
            )
        else:
            key = (uri, ref.version)
            if key not in clones:
                clone_dir = clone_library(
                    uri, ref.version, _new_dir(tmp / f"clone-{len(clones)}")
                )
                clones[key] = (clone_dir, library_commit(clone_dir))
            clone_dir, commit = clones[key]
            pattern_dir = cloned_pattern(clone_dir, ref.name, uri, ref.version)
        fetched.append(
            _Fetched(
                ref=ref,
                library=ref.library,
                pattern_dir=pattern_dir,
                source=source_label(uri),
                commit=commit,
            )
        )
    return fetched


def _new_dir(path: Path) -> Path:
    path.mkdir(parents=True)
    return path


def _destination(file_name: str, library: str) -> Path | None:
    """The folder an installed file goes in, chosen by its name."""
    if file_name.endswith(SUPPORT_YAML_SUFFIX):
        return GLOBALS.IBEK_DEFS
    if file_name.endswith(PVI_SUFFIX):
        return GLOBALS.PVI_DEFS
    if file_name.endswith(PROTOCOL_SUFFIXES):
        return GLOBALS.SUPPORT_PROTOCOL
    if file_name.endswith(DATABASE_SUFFIXES + (REQ_SUFFIX,)):
        return GLOBALS.SUPPORT / library / "db"
    return None


def _defined_module(path: Path, pattern: str) -> str:
    try:
        module = support_yaml_module(path)
    except (OSError, YAMLError) as exc:
        raise PatternError(f"{pattern}: cannot read {path.name}: {exc}") from exc
    if not module:
        raise PatternError(f"{pattern}: {path.name} declares no module")
    return module


def _image_modules() -> dict[str, Path]:
    """Every module the image's support YAML defines, and the file defining it."""
    modules: dict[str, Path] = {}
    for path in sorted(GLOBALS.IBEK_DEFS.rglob(f"*{SUPPORT_YAML_SUFFIX}")):
        try:
            module = support_yaml_module(path)
        except (OSError, YAMLError) as exc:
            raise PatternError(f"cannot read the module of {path}: {exc}") from exc
        if module:
            modules.setdefault(module, path)
    return modules


class _Planner:
    """Plans the placements of one run, refusing anything that would collide."""

    def __init__(self) -> None:
        self.modules: dict[str, str] = {
            module: str(path) for module, path in _image_modules().items()
        }
        self.owners: dict[Path, str] = {}
        # database and req file names this run installs, across every library
        self.names: dict[str, Path] = {}
        self._support_reqs: dict[str, Path] | None = None
        self.placements: list[_Placement] = []
        self.pattern_modules: dict[str, list[str]] = {}

    def support_reqs(self) -> dict[str, Path]:
        """Every req file under SUPPORT by name; read once, when first needed."""
        if self._support_reqs is None:
            self._support_reqs = {}
            for path in sorted(GLOBALS.SUPPORT.rglob(f"*{REQ_SUFFIX}")):
                self._support_reqs.setdefault(path.name, path)
        return self._support_reqs

    def plan(self, fetched: _Fetched) -> None:
        name = fetched.ref.name
        selected = plan_vendor(fetched.pattern_dir)
        support = [src for src, _ in selected if src.name.endswith(SUPPORT_YAML_SUFFIX)]
        if not support:
            raise PatternError(f"{name}: selects no *{SUPPORT_YAML_SUFFIX}")
        modules = []
        for path in support:
            module = _defined_module(path, name)
            if module in self.modules:
                raise PatternError(
                    f"{name}: module {module!r} is already defined by "
                    f"{self.modules[module]}"
                )
            self.modules[module] = f"pattern {name} ({path.name})"
            modules.append(module)
        self.pattern_modules[name] = sorted(modules)
        for src, _ in selected:
            self._place(name, fetched.library, src)

    def _place(self, name: str, library: str, src: Path) -> None:
        file_name = src.name
        folder = _destination(file_name, library)
        if folder is None:
            raise PatternError(
                f"{name}: no install location for {file_name}; install takes "
                f"*{SUPPORT_YAML_SUFFIX}, *{PVI_SUFFIX}, "
                f"{', '.join('*' + s for s in PROTOCOL_SUFFIXES)}, "
                f"{', '.join('*' + s for s in DATABASE_SUFFIXES)} and *{REQ_SUFFIX}"
            )
        target = folder / file_name
        if target.exists() or target.is_symlink():
            raise PatternError(f"{name}: {target} already exists")
        if target in self.owners:
            other = self.owners[target]
            raise PatternError(
                f"{name}: {target} is installed twice by this pattern"
                if other == name
                else f"{name} and {other} both install {target}"
            )
        if file_name.endswith(DATABASE_SUFFIXES):
            # msi takes the first match on its ${SUPPORT}/*/db include path
            for other_path in sorted(GLOBALS.SUPPORT.glob(f"*/db/{file_name}")):
                raise PatternError(
                    f"{name}: {file_name} is also installed as {other_path}; msi "
                    "would load whichever it finds first"
                )
            self._refuse_planned_name(name, target)
        elif file_name.endswith(REQ_SUFFIX):
            # autosave keeps a req file already linked in AUTOSAVE, and
            # otherwise links the first of a name it finds under SUPPORT
            other_path = self.support_reqs().get(file_name)
            link = GLOBALS.AUTOSAVE / file_name
            if other_path is None and (link.exists() or link.is_symlink()):
                other_path = link
            if other_path is not None:
                raise PatternError(
                    f"{name}: {file_name} is also installed as {other_path}; "
                    "autosave would use only one of them"
                )
            self._refuse_planned_name(name, target)
        self.owners[target] = name
        self.placements.append(_Placement(pattern=name, source=src, target=target))

    def _refuse_planned_name(self, name: str, target: Path) -> None:
        other = self.names.get(target.name)
        if other is not None:
            raise PatternError(
                f"{name}: {target} and {other} have the same name; only one of "
                "them would be found"
            )
        self.names[target.name] = target


def install(
    refs: list[str],
    source_override: str | None = None,
    extra_libraries: dict[str, str] | None = None,
) -> list[str]:
    """Install ``refs`` into the image under ``EPICS_ROOT``; return their names.

    The lock is read first, so an unreadable one aborts before anything is
    fetched. Every pattern is then fetched and every placement planned and
    checked; only when all of them pass is any file written, followed by the
    lock.
    """
    lock = ImageLock(GLOBALS.IMAGE_PATTERN_LOCK)
    parsed = parse_install_refs(refs)
    for ref in parsed:
        if ref.name in lock.patterns:
            entry = lock.patterns[ref.name]
            raise PatternError(
                f"pattern {ref.name!r} is already installed in this image "
                f"({entry.library}@{entry.version})"
            )
    with tempfile.TemporaryDirectory() as tmp:
        fetched = _fetch_all(parsed, source_override, extra_libraries, Path(tmp))
        planner = _Planner()
        for item in fetched:
            planner.plan(item)
        files: dict[str, dict[str, str]] = {item.ref.name: {} for item in fetched}
        for placement in planner.placements:
            # The hash is taken from the bytes read, not a re-read of the
            # target, as for `add`.
            data = placement.source.read_bytes()
            placement.target.parent.mkdir(parents=True, exist_ok=True)
            placement.target.write_bytes(data)
            key = placement.target.relative_to(GLOBALS.EPICS_ROOT).as_posix()
            files[placement.pattern][key] = file_hash(data)
    for item in fetched:
        name = item.ref.name
        assert item.ref.version  # parse_install_refs guarantees it
        lock.patterns[name] = InstalledPattern(
            library=item.library,
            version=item.ref.version,
            source=item.source,
            commit=item.commit,
            modules=planner.pattern_modules[name],
            files=files[name],
        )
    lock.save()
    return [item.ref.name for item in fetched]


def check_image(allow_dirty: bool = False) -> CheckResult:
    """Verify the installed pattern files against the image lock."""
    result = CheckResult()
    try:
        lock = ImageLock(GLOBALS.IMAGE_PATTERN_LOCK)
    except PatternError as exc:
        result.failures.append(str(exc))
        return result
    for name, entry in lock.patterns.items():
        for rel, expected in entry.files.items():
            target = GLOBALS.EPICS_ROOT / rel
            if not target.is_file():
                result.failures.append(f"{name}:{target} missing installed file")
                continue
            actual = file_hash(target.read_bytes())
            if actual != expected:
                result.failures.append(
                    f"{name}:{target} hash mismatch (expected {expected}, got {actual})"
                )
    if allow_dirty:
        result.warnings.extend(result.failures)
        result.failures = []
    return result
