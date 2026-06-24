"""
Vendoring orchestration for ``ibek pattern`` — add / update / check / restore.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ibek.globals import RUNTIME_LOCK_NAME

from .lock import RuntimeLock, file_hash, is_dirty, stamp_content
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
    """Outcome of ``ibek pattern check`` for one instance."""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.failures


def _config_dir(instance_dir: Path) -> Path:
    return instance_dir / "config"


def _lock_path(instance_dir: Path) -> Path:
    return instance_dir / RUNTIME_LOCK_NAME


def _vendor_files(
    pattern_dir: Path, config_dir: Path, source: str, version: str
) -> dict[str, str]:
    """Stamp + write every file in ``pattern_dir`` into ``config_dir``.

    Returns the ``relpath -> sha256`` map for the lock.
    """
    files: dict[str, str] = {}
    for src in sorted(p for p in pattern_dir.rglob("*") if p.is_file()):
        rel = src.relative_to(pattern_dir)
        stamped = stamp_content(rel, src.read_bytes(), source, version)
        dest = config_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(stamped)
        files[str(rel)] = file_hash(stamped)
    return files


def _do_vendor(
    ref: PatternRef,
    instance_dir: Path,
    source_override: str | None,
    extra_libraries: dict[str, str] | None,
) -> tuple[str, str, dict[str, str]]:
    """Fetch + vendor ``ref`` into the instance; return (source_label, version, files)."""
    uri, candidates = resolve_source(ref, source_override, extra_libraries)
    config_dir = _config_dir(instance_dir)
    config_dir.mkdir(parents=True, exist_ok=True)

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
            files = _vendor_files(pattern_dir, config_dir, label, ref.version or "HEAD")
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
    instance_dir: Path,
    source_override: str | None = None,
    extra_libraries: dict[str, str] | None = None,
) -> None:
    """Vendor a pattern into ``instance_dir`` and write the lock + schema."""
    ref = parse_ref(qualified)
    label, version, files = _do_vendor(
        ref, instance_dir, source_override, extra_libraries
    )
    lock = RuntimeLock(_lock_path(instance_dir))
    lock.set_pattern(ref.name, version, label, files)
    lock.save()
    generate_instance_schema(instance_dir)


def update(
    name: str | None,
    instance_dir: Path,
    version: str | None = None,
    source_override: str | None = None,
    extra_libraries: dict[str, str] | None = None,
) -> None:
    """Re-vendor one (or all) patterns, optionally moving the pinned version."""
    lock = RuntimeLock(_lock_path(instance_dir))
    if not lock.patterns:
        raise PatternError(f"no patterns to update in {instance_dir}")
    names = [name] if name else list(lock.patterns)
    for pattern_name in names:
        if pattern_name not in lock.patterns:
            raise PatternError(f"pattern {pattern_name!r} not in lock")
        existing = lock.patterns[pattern_name]
        new_version = version or existing.version
        ref = PatternRef(name=pattern_name, version=new_version)
        label, resolved_version, files = _do_vendor(
            ref, instance_dir, source_override or existing.source, extra_libraries
        )
        lock.set_pattern(pattern_name, resolved_version, label, files)
    lock.save()
    generate_instance_schema(instance_dir)


def restore(
    name: str | None,
    instance_dir: Path,
    extra_libraries: dict[str, str] | None = None,
) -> None:
    """Revert vendored files to the pinned version recorded in the lock."""
    lock = RuntimeLock(_lock_path(instance_dir))
    if not lock.patterns:
        raise PatternError(f"no patterns to restore in {instance_dir}")
    names = [name] if name else list(lock.patterns)
    config_dir = _config_dir(instance_dir)
    for pattern_name in names:
        if pattern_name not in lock.patterns:
            raise PatternError(f"pattern {pattern_name!r} not in lock")
        entry = lock.patterns[pattern_name]
        ref = PatternRef(name=pattern_name, version=entry.version)
        with tempfile.TemporaryDirectory() as tmp:
            pattern_dir = fetch_pattern(
                _restore_uri(entry.source, extra_libraries),
                ref.name,
                ref.version,
                Path(tmp),
            )
            _vendor_files(pattern_dir, config_dir, entry.source, entry.version)
    generate_instance_schema(instance_dir)


def _restore_uri(source: str, extra_libraries: dict[str, str] | None) -> str:
    """Map a recorded lock ``source`` label back to a fetchable URI."""
    from .sources import library_registry

    for uri in library_registry(extra_libraries).values():
        if source_label(uri) == source:
            return uri
    # The label is itself a host/path; reconstruct an https URL for github.
    if source.startswith("github.com/"):
        return "https://" + source
    return source


def check(
    instance_dir: Path,
    allow_dirty: bool = False,
) -> CheckResult:
    """Verify vendored files against the lock for one instance."""
    result = CheckResult()
    lock = RuntimeLock(_lock_path(instance_dir))
    config_dir = _config_dir(instance_dir)
    for pattern_name, entry in lock.patterns.items():
        for rel, expected in entry.files.items():
            target = config_dir / rel
            if is_dirty(expected):
                reason = expected.partition("#")[2].strip() or "no reason given"
                result.warnings.append(f"{pattern_name}:{rel} marked DIRTY ({reason})")
                continue
            if not target.exists():
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
