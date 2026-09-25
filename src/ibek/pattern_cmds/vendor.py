"""
Vendoring orchestration for ``ibek pattern`` — add / update / check / restore.
"""

from __future__ import annotations

import tempfile
from collections.abc import Set as AbstractSet
from pathlib import Path, PurePosixPath

from ibek.globals import RUNTIME_LOCK_NAME

from .lock import RuntimeLock, Selection, file_hash, is_dirty
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


def _owned_by(path: Path, dest_root: Path, orphans: set[str]) -> bool:
    """True if every file at or beneath ``path`` is one of ``orphans``.

    ``orphans`` are the destination-relative keys this pattern's previous lock
    entry vendored and the new plan drops, so such a path is this pattern's to
    remove. A symlink counts as a file, and is never followed.
    """
    if path.is_symlink() or not path.is_dir():
        return path.relative_to(dest_root).as_posix() in orphans
    return all(_owned_by(child, dest_root, orphans) for child in sorted(path.iterdir()))


def _blocking_paths(
    plan: list[tuple[Path, str]], dest_root: Path, orphans: set[str]
) -> list[Path]:
    """Return the paths on disk that stand where the plan must write, or raise.

    ``plan_vendor`` guarantees the plan is self-consistent; it cannot know what
    is already on disk. A file where the plan needs a folder, or a folder where
    it needs a file, would otherwise abort the write half way with a raw
    ``FileExistsError`` or ``IsADirectoryError``.

    Such a path holding only this pattern's ``orphans`` is returned, for
    :func:`_clear_blocking_paths` to remove; one holding anything else (another
    pattern's files, user files) is refused before anything is written.
    """
    blocking: dict[Path, None] = {}
    for _, rel in plan:
        parts = PurePosixPath(rel).parts
        for depth in range(1, len(parts)):
            parent = dest_root.joinpath(*parts[:depth])
            if parent.exists() and not parent.is_dir():
                if not _owned_by(parent, dest_root, orphans):
                    raise PatternError(
                        f"cannot vendor {rel!r}: {parent} already exists and is "
                        "not a directory; remove it and re-run"
                    )
                blocking[parent] = None
                break
        else:
            target = dest_root / rel
            if target.is_dir():
                if not _owned_by(target, dest_root, orphans):
                    raise PatternError(
                        f"cannot vendor {rel!r}: {target} already exists and is a "
                        "directory; remove it and re-run"
                    )
                blocking[target] = None
    return list(blocking)


def _clear_blocking_paths(blocking: list[Path]) -> None:
    """Remove paths that :func:`_blocking_paths` found hold only orphans."""
    for path in blocking:
        if path.is_symlink() or not path.is_dir():
            path.unlink(missing_ok=True)
            continue
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_dir() and not child.is_symlink():
                child.rmdir()
            else:
                child.unlink()
        path.rmdir()


def _vendor_files(
    plan: list[tuple[Path, str]],
    dest_root: Path,
    orphans: AbstractSet[str] = frozenset(),
) -> dict[str, str]:
    """Write every planned file into ``dest_root``; return the lock's hash map.

    ``orphans`` are the keys this pattern's previous lock entry vendored that
    the plan drops. Any of them standing where the plan writes (a file where a
    folder must go, or a folder where a file must go) is removed first; every
    other path in the way is refused before anything is written.

    Read -> write -> hash, with **nothing** permitted to transform the bytes in
    between: the recorded SHA-256 is taken from the bytes read out of the library
    (not from a re-read of the target), so "vendored bytes == library bytes" holds
    by construction. Any future post-write step would record a hash that no longer
    matches disk and make ``check`` fail on a freshly vendored tree.
    """
    blocking = _blocking_paths(plan, dest_root, set(orphans))
    _clear_blocking_paths(blocking)
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

    An orphan already gone is skipped, including one whose parent is now a file
    (a previous folder destination that the new plan writes as a file).

    Lock keys are free-form destination-relative strings, so containment in
    ``dest_root`` is enforced rather than assumed — both for the unlink and for
    the walk up through newly-empty parents.
    """
    root = dest_root.resolve()
    for rel in sorted(orphans):
        target = (root / rel).resolve()
        if root not in target.parents:
            continue  # a key that escapes the destination root is never touched
        if not target.parent.is_dir():
            continue  # its folder is gone, or is now a vendored file
        if target.is_dir():
            continue  # a folder is never an orphan; its files are pruned by key
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
    select: Selection | None = None,
    old_files: AbstractSet[str] = frozenset(),
) -> tuple[str, str, dict[str, str]]:
    """Fetch + vendor ``ref`` into the destination; return (label, version, files).

    ``select`` is the destination's adjustment to the manifest's file-set,
    applied by ``plan_vendor``. ``old_files`` are the keys the pattern's
    previous lock entry vendored; those the new plan drops are removed, so the
    destination holds exactly the new file-set whatever file and folder shapes
    the previous one left.

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
            select = select or Selection()
            plan = plan_vendor(pattern_dir, select.include, select.exclude)
            orphans = set(old_files) - {key for _, key in plan}
            files = _vendor_files(plan, dest_dir, orphans)
            _prune_orphans(dest_dir, orphans)
            return label, ref.version or "HEAD", files
    raise PatternError(
        f"could not resolve pattern {ref.name!r}: {last_error or 'no libraries'}"
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
    select: Selection | None = None,
) -> None:
    """Vendor a pattern into ``dest_dir`` and write the lock + schema.

    ``select`` is recorded in the lock as given, replacing any selection the
    pattern had, so ``update`` and ``restore`` reproduce the same file-set.

    The lock is read *before* anything is vendored, so an unreadable one aborts
    before a file is written. Re-adding an already-locked pattern prunes the
    files the new file-set no longer produces, exactly as ``update`` does — an
    allow-list manifest makes that the difference between a clean destination and
    excluded files lingering untracked by ``check``.
    """
    ref = parse_ref(qualified)
    lock = RuntimeLock(_lock_path(dest_dir))
    old_files = lock.vendored_keys(ref.name) if ref.name in lock.patterns else set()
    label, version, files = _do_vendor(
        ref, dest_dir, source_override, extra_libraries, select, old_files
    )
    lock.set_pattern(ref.name, version, label, files, select)
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
    select: Selection | None,
) -> tuple[str, str, dict[str, str]]:
    """Re-fetch an already-locked pattern and rewrite its files in place.

    The single fetch path shared by update and restore, so they can never
    diverge on how a recorded ``source`` is resolved. ``source`` (a lock label
    or an explicit override) is normalised to a fetchable URI inside
    ``_do_vendor``, which also removes the files dropped relative to
    ``old_files``. Both lists are in the same coordinate system
    (destination-root-relative). Returns the ``(label, version, files)`` the caller
    records — restore discards it and leaves the lock untouched, since its
    rewritten bytes reproduce the pin. ``select`` is the lock's recorded
    selection, reapplied so the file-set matches the one the lock records.
    """
    ref = PatternRef(name=name, version=version)
    label, resolved_version, files = _do_vendor(
        ref, dest_dir, source, extra_libraries, select, old_files
    )
    return label, resolved_version, files


def update(
    name: str | None,
    dest_dir: Path,
    version: str | None = None,
    source_override: str | None = None,
    extra_libraries: dict[str, str] | None = None,
) -> None:
    """Re-vendor one (or all) patterns, optionally moving the pinned version.

    Re-fetches each pattern at its pinned (or new) version and rewrites the
    lock whole, with destination-root-relative keys and hashes over the
    library's bytes.
    """
    lock = RuntimeLock(_lock_path(dest_dir))
    names = _locked_names(lock, name, "update")
    for pattern_name in names:
        existing = lock.patterns[pattern_name]
        label, resolved_version, files = _revendor(
            dest_dir,
            pattern_name,
            version or existing.version,
            source_override or existing.source,
            lock.vendored_keys(pattern_name),
            extra_libraries,
            existing.select,
        )
        lock.set_pattern(pattern_name, resolved_version, label, files, existing.select)
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
            entry.select,
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
        for rel, expected in entry.files.items():
            target = dest_dir / rel
            if is_dirty(expected):
                reason = expected.partition("#")[2].strip() or "no reason given"
                result.warnings.append(f"{pattern_name}:{rel} marked DIRTY ({reason})")
                continue
            if not target.is_file():
                result.failures.append(f"{pattern_name}:{rel} missing vendored file")
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
