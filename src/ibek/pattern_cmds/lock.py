"""
The ``runtime-lock.yaml`` integrity lock for vendored runtime-support patterns.

A pattern is an arbitrary file-set (``*.ibek.support.yaml`` plus optional
proto / template / db / req / ...) vendored from a central library at a pinned
version. ``ibek pattern`` injects a deterministic ``# Vendored from ...`` header
into each file *before* hashing, so the recorded SHA-256 covers the file exactly
as written to disk and ``ibek pattern check`` is a trivial ``sha256(file) == lock``.
"""

from __future__ import annotations

import hashlib
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML

from ibek.globals import BaseSettings

# The deterministic vendored-file header. No timestamps or absolute paths so the
# header (and therefore the hash) is reproducible. ``#`` is a comment in every
# format a pattern currently carries (yaml / proto / template / db / req).
VENDOR_HEADER_TEMPLATE = "{comment} Vendored from {source}@{version} — DO NOT EDIT"

# Map a file suffix to its line-comment prefix. ``#`` is the default and covers
# all current pattern file types; extend here when a comment-less format appears.
COMMENT_PREFIXES: dict[str, str] = {
    ".proto": "#",
    ".protocol": "#",
    ".template": "#",
    ".substitutions": "#",
    ".db": "#",
    ".req": "#",
    ".yaml": "#",
    ".yml": "#",
    ".cmd": "#",
}
DEFAULT_COMMENT_PREFIX = "#"

# A lock entry whose hash is replaced by a string starting with this marker is a
# deliberately, visibly dirty file (e.g. testing a fix against real hardware).
DIRTY_MARKER = "DIRTY"


def comment_prefix(path: Path) -> str | None:
    """Return the line-comment prefix for ``path``, or None if comment-less.

    A None result means no header can be injected for this file type; the file
    is still vendored and hashed, just without a provenance header.
    """
    return COMMENT_PREFIXES.get(path.suffix, DEFAULT_COMMENT_PREFIX)


def vendored_header(path: Path, source: str, version: str) -> str | None:
    """Build the deterministic vendored header line for ``path``."""
    prefix = comment_prefix(path)
    if prefix is None:
        return None
    return VENDOR_HEADER_TEMPLATE.format(comment=prefix, source=source, version=version)


def stamp_content(rel_path: Path, content: bytes, source: str, version: str) -> bytes:
    """Inject the vendored header at the top of ``content`` (idempotent shape).

    The header is prepended as the first line; the original pristine content
    (no header upstream) follows unchanged. Returns the exact bytes to write.
    """
    header = vendored_header(rel_path, source, version)
    if header is None:
        return content
    return (header + "\n").encode() + content


def file_hash(data: bytes) -> str:
    """Return the ``sha256:<hex>`` digest of ``data``."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def is_dirty(value: str) -> bool:
    """True if a lock file-entry value is a deliberate DIRTY marker."""
    return value.strip().startswith(DIRTY_MARKER)


class PatternEntry(BaseSettings):
    """One vendored pattern's lock record."""

    version: str
    source: str
    files: dict[str, str]


class RuntimeLock:
    """Read/modify/write a ``runtime-lock.yaml`` at an IOC instance root."""

    def __init__(self, path: Path):
        self.path = path
        self.patterns: dict[str, PatternEntry] = {}
        if path.exists():
            self.load()

    def load(self) -> None:
        raw = YAML(typ="safe").load(self.path) or {}
        self.patterns = {name: PatternEntry(**entry) for name, entry in raw.items()}

    def set_pattern(
        self, name: str, version: str, source: str, files: dict[str, str]
    ) -> None:
        self.patterns[name] = PatternEntry(version=version, source=source, files=files)

    def remove_pattern(self, name: str) -> None:
        self.patterns.pop(name, None)

    def save(self) -> None:
        data = {
            name: {
                "version": entry.version,
                "source": entry.source,
                "files": dict(entry.files),
            }
            for name, entry in self.patterns.items()
        }
        yaml = YAML()
        yaml.default_flow_style = False
        if not data:
            # An empty lock is removed rather than left as an empty document.
            if self.path.exists():
                self.path.unlink()
            return
        stream = StringIO()
        yaml.dump(data, stream)
        self.path.write_text(stream.getvalue())
