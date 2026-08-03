"""
Vendoring orchestration for ``ibek pattern`` — add / update / check / restore.
"""

from __future__ import annotations

import tempfile
from pathlib import Path, PurePosixPath

from ibek.globals import RUNTIME_LOCK_NAME

from .lock import RuntimeLock, file_hash, is_dirty
from .manifest import plan_vendor
from .schema import generate_instance_schema
from .sources import (
    PatternError,
    PatternRef,
    fetch_pattern,
    parse_ref,
    resolve_source,
    source_label,
)


class CheckResult:
    """Outcome of ``ibek pattern check`` for one destination."""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.failures


def _lock_path(dest_dir: Path) -> Path:
    return dest_dir / RUNTIME_LOCK_NAME


def _refuse_blocked_targets(plan: list[tuple[Path, str]], dest_root: Path) -> None:
    """Refuse a plan the destination cannot hold, before anything is written.

    ``plan_vendor`` guarantees the plan is self-consistent; it cannot know what
    is already on disk. A previously vendored *file* where the new version needs
    a *directory* (upstream replaced ``db`` with ``db/``) would otherwise abort
    ``mkdir`` half way through the write with a raw ``FileExistsError``, leaving a
    half-vendored tree and no lock — invisible to ``check``.
    """
    for _, rel in plan:
        parts = PurePosixPath(rel).parts
        for depth in range(1, len(parts)):
            parent = dest_root.joinpath(*parts[:depth])
            if parent.exists() and not parent.is_dir():
                raise PatternError(
                    f"cannot vendor {rel!r}: {parent} already exists and is not a "
                    "directory; remove it and re-run"
                )
        target = dest_root / rel
        if target.is_dir():
            raise PatternError(
                f"cannot vendor {rel!r}: {target} already exists and is a directory; "
                "remove it and re-run"
            )


def _vendor_files(plan: list[tuple[Path, str]], dest_root: Path) -> dict[str, str]:
    """Write every planned file into ``dest_root``; return the lock's hash map.

    Read -> write -> hash, with **nothing** permitted to transform the bytes in
    between: the recorded SHA-256 is taken from the bytes read out of the library
    (not from a re-read of the target), so "vendored bytes == library bytes" holds
    by construction. Any future post-write step would record a hash that no longer
    matches disk and make ``check`` fail on a freshly vendored tree.
    """
    _refuse_blocked_targets(plan, dest_root)
    files: dict[str, str] = {}
    for src, rel in plan:
        data = src.read_bytes()
        target = dest_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files[rel] = file_hash(data)
    return files


def _prune_orphans(dest_root: Path, orphans: set[str]) -> None:
    """Delete files the previous lock vendored that the new file-set dropped.

    Removes each orphaned path and any parent directories it leaves empty, so a
    file renamed/removed upstream (or dropped by a manifest change) cannot linger
    under the destination and be placed into the IOC by
    ``ibek runtime place-files`` at boot. Scoped to one pattern's prior ``files``
    keys, so it never touches another pattern's or user-authored files.

    Lock keys are free-form destination-relative strings, so containment in
    ``dest_root`` is enforced rather than assumed — both for the unlink and for
    the walk up through newly-empty parents.
    """
    root = dest_root.resolve()
    for rel in sorted(orphans):
        target = (root / rel).resolve()
        if root not in target.parents:
            continue  # a key that escapes the destination root is never touched
        target.unlink(missing_ok=True)
        parent = target.parent
        while root in parent.parents and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent


def _do_vendor(
    ref: PatternRef,
    dest_dir: Path,
    source_override: str | None,
    extra_libraries: dict[str, str] | None,
) -> tuple[str, str, dict[str, str]]:
    """Fetch + vendor ``ref`` into the destination; return (label, version, files).

    An explicit ``source_override`` (a user ``--source`` or a recorded lock
    label) is normalised to a fetchable URI here — the single point every caller
    (add / update / restore) shares, so none can clone a scheme-stripped label.

    The order is fetch -> validate the whole manifest -> plan and validate every
    destination -> only then write. ``plan_vendor`` is deliberately outside the
    probe loop's ``except PatternError``: a ``ManifestError`` is a PatternError,
    and swallowing it there would silently degrade a broken manifest into
    "could not resolve pattern X".
    """
    if source_override:
        source_override = _source_uri(source_override, extra_libraries)
    uri, candidates = resolve_source(ref, source_override, extra_libraries)

    last_error: Exception | None = None
    sources = [uri] if uri else _candidate_uris(candidates, extra_libraries)
    for candidate_uri in sources:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                pattern_dir = fetch_pattern(
                    candidate_uri, ref.name, ref.version, Path(tmp)
                )
            except PatternError as exc:
                last_error = exc
                continue
            label = source_label(candidate_uri)
            plan = plan_vendor(pattern_dir)
            files = _vendor_files(plan, dest_dir)
            return label, ref.version or "HEAD", files
    raise PatternError(
        f"could not resolve pattern {ref.name!r}: {last_error or 'no libraries'}"
    )


def _refuse_partial_rewrite(lock: RuntimeLock, refreshed: set[str]) -> None:
    """Refuse to rewrite only part of a pre-wrapper lock.

    ``save()`` writes the current format for *every* entry, so re-vendoring one
    pattern of an old lock would leave the rest wearing a format they do not
    have — config/-relative keys and hashes covering the removed header, now
    indistinguishable from current ones and no longer able to explain themselves
    to ``check``. Re-vendoring the whole lock is what makes it consistent, and is
    exactly what a bare ``ibek pattern update`` does.
    """
    stale = sorted(set(lock.patterns) - refreshed)
    if lock.legacy and stale:
        raise PatternError(
            f"{lock.path} predates destination-root-relative lock keys, and this "
            f"would leave {', '.join(stale)} half-rewritten; "
            "run 'ibek pattern update' (all patterns) first"
        )


def _candidate_uris(
    libraries: list[str], extra_libraries: dict[str, str] | None
) -> list[str]:
    from .sources import library_registry

    registry = library_registry(extra_libraries)
    return [registry[name] for name in libraries if name in registry]


def add(
    qualified: str,
    dest_dir: Path,
    source_override: str | None = None,
    extra_libraries: dict[str, str] | None = None,
) -> None:
    """Vendor a pattern into ``dest_dir`` and write the lock + schema.

    The lock is read *before* anything is vendored, so an unreadable one aborts
    before a file is written. Re-adding an already-locked pattern prunes the
    files the new file-set no longer produces, exactly as ``update`` does — an
    allow-list manifest makes that the difference between a clean destination and
    excluded files lingering untracked by ``check``.
    """
    ref = parse_ref(qualified)
    lock = RuntimeLock(_lock_path(dest_dir))
    _refuse_partial_rewrite(lock, {ref.name})
    old_files = lock.vendored_keys(ref.name) if ref.name in lock.patterns else set()
    label, version, files = _do_vendor(ref, dest_dir, source_override, extra_libraries)
    _prune_orphans(dest_dir, old_files - set(files))
    lock.set_pattern(ref.name, version, label, files)
    lock.save()
    generate_instance_schema(dest_dir)


def _locked_names(lock: RuntimeLock, name: str | None, verb: str) -> list[str]:
    """Resolve a ``--name`` (or all patterns) against the lock, validating each."""
    if not lock.patterns:
        raise PatternError(f"no patterns to {verb} in {lock.path.parent}")
    names = [name] if name else list(lock.patterns)
    for pattern_name in names:
        if pattern_name not in lock.patterns:
            raise PatternError(f"pattern {pattern_name!r} not in lock")
    return names


def _revendor(
    dest_dir: Path,
    name: str,
    version: str | None,
    source: str,
    old_files: set[str],
    extra_libraries: dict[str, str] | None,
) -> tuple[str, str, dict[str, str]]:
    """Re-fetch an already-locked pattern and rewrite its files in place.

    The single fetch path shared by update and restore, so they can never
    diverge on how a recorded ``source`` is resolved. ``source`` (a lock label
    or an explicit override) is normalised to a fetchable URI inside
    ``_do_vendor``; files dropped relative to ``old_files`` are pruned. Both
    lists are in the same coordinate system (destination-root-relative), so a
    file kept under a new destination has its old key pruned only after the new
    key has been written. Returns the ``(label, version, files)`` the caller
    records — restore discards it and leaves the lock untouched, since its
    rewritten bytes reproduce the pin.
    """
    ref = PatternRef(name=name, version=version)
    label, resolved_version, files = _do_vendor(ref, dest_dir, source, extra_libraries)
    _prune_orphans(dest_dir, old_files - set(files))
    return label, resolved_version, files


def update(
    name: str | None,
    dest_dir: Path,
    version: str | None = None,
    source_override: str | None = None,
    extra_libraries: dict[str, str] | None = None,
) -> None:
    """Re-vendor one (or all) patterns, optionally moving the pinned version.

    A bare ``update`` is the documented recovery from a pre-wrapper lock: it
    re-fetches every pattern at its pinned version and rewrites the lock whole,
    with destination-root-relative keys and hashes over the library's bytes.
    """
    lock = RuntimeLock(_lock_path(dest_dir))
    names = _locked_names(lock, name, "update")
    _refuse_partial_rewrite(lock, set(names))
    for pattern_name in names:
        existing = lock.patterns[pattern_name]
        label, resolved_version, files = _revendor(
            dest_dir,
            pattern_name,
            version or existing.version,
            source_override or existing.source,
            lock.vendored_keys(pattern_name),
            extra_libraries,
        )
        lock.set_pattern(pattern_name, resolved_version, label, files)
    lock.save()
    generate_instance_schema(dest_dir)


def restore(
    name: str | None,
    dest_dir: Path,
    extra_libraries: dict[str, str] | None = None,
) -> None:
    """Revert vendored files to the pinned version recorded in the lock."""
    lock = RuntimeLock(_lock_path(dest_dir))
    for pattern_name in _locked_names(lock, name, "restore"):
        entry = lock.patterns[pattern_name]
        _revendor(
            dest_dir,
            pattern_name,
            entry.version,
            entry.source,
            lock.vendored_keys(pattern_name),
            extra_libraries,
        )
    generate_instance_schema(dest_dir)


def _source_uri(source: str, extra_libraries: dict[str, str] | None) -> str:
    """Map a recorded lock ``source`` label back to a fetchable URI.

    The lock stores the scheme-stripped label (``source_label``), so a github
    source must be turned back into an https URL before it is handed to
    ``git clone``. Idempotent on a source that is already a full URI or path.
    """
    from .sources import library_registry

    for uri in library_registry(extra_libraries).values():
        if source_label(uri) == source:
            return uri
    # The label is itself a host/path; reconstruct an https URL for github.
    if source.startswith("github.com/"):
        return "https://" + source
    return source


# Emitted for a pre-wrapper lock, whose keys are config/-relative and whose
# hashes still cover the vendored header that no longer exists: neither its paths
# nor its digests can be verified, and re-vendoring is the only way back.
LEGACY_KEYS_HINT = (
    "this lock predates destination-root-relative keys (no 'patterns:' root key) "
    "and its hashes cover the removed vendored header; "
    "run 'ibek pattern update' to rewrite it"
)


def check(
    dest_dir: Path,
    allow_dirty: bool = False,
) -> CheckResult:
    """Verify vendored files against the lock for one destination."""
    result = CheckResult()
    try:
        lock = RuntimeLock(_lock_path(dest_dir))
    except PatternError as exc:
        # Returned before the allow_dirty fold: a lock that could not be read
        # verified nothing, and must not be downgradable to a warning.
        result.failures.append(str(exc))
        return result
    for pattern_name, entry in lock.patterns.items():
        hinted = False
        for rel, expected in entry.files.items():
            target = dest_dir / rel
            if is_dirty(expected):
                reason = expected.partition("#")[2].strip() or "no reason given"
                result.warnings.append(f"{pattern_name}:{rel} marked DIRTY ({reason})")
                continue
            if not target.exists():
                result.failures.append(f"{pattern_name}:{rel} missing vendored file")
                # Once per pattern, and only for a lock that really is old: a
                # current lock may legitimately hold a root-level key, and
                # telling its owner to "fix" it would be a lie.
                if lock.legacy and not hinted:
                    result.failures.append(f"{pattern_name}: {LEGACY_KEYS_HINT}")
                    hinted = True
                continue
            actual = file_hash(target.read_bytes())
            if actual != expected:
                result.failures.append(
                    f"{pattern_name}:{rel} hash mismatch "
                    f"(expected {expected}, got {actual})"
                )
    if allow_dirty:
        result.warnings.extend(result.failures)
        result.failures = []
    return result
