"""
The ``runtime-lock.yaml`` integrity lock for vendored runtime-support patterns.

A pattern is an arbitrary file-set (``*.ibek.support.yaml`` plus optional
proto / template / db / req / ...) vendored from a central library at a pinned
version. Vendored files are byte-identical to the library at its tag — nothing
is injected or rewritten on the way in — so the recorded SHA-256 covers the
upstream bytes verbatim and ``ibek pattern check`` is a trivial
``sha256(file) == lock``.

Keys under a pattern's ``files`` are relative to the **destination root**, not to
``config/``. Legacy behaviour (everything into ``config/``) produces ``config/...``
keys naturally via the manifest default, so there is no per-pattern base field
and no branch in ``check``.

A lock written before the ``version:`` / ``patterns:`` root wrapper is still
*read* — as :attr:`RuntimeLock.legacy` — because the documented recovery from one
is ``ibek pattern update``, and update cannot rewrite a lock it refuses to open.
"""

from __future__ import annotations

import hashlib
from io import StringIO
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ibek.globals import BaseSettings

from .sources import PatternError

# The lock's root ``version:``. This exists so the on-disk format can evolve; it
# is deliberately *not* a migration mechanism (see ADR 0005).
LOCK_VERSION = 1
SUPPORTED_LOCK_VERSIONS = frozenset({1})

# A lock entry whose hash is replaced by a string starting with this marker is a
# deliberately, visibly dirty file (e.g. testing a fix against real hardware).
DIRTY_MARKER = "DIRTY"


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
    """Read/modify/write a ``runtime-lock.yaml`` at a destination root."""

    def __init__(self, path: Path):
        self.path = path
        self.patterns: dict[str, PatternEntry] = {}
        # True when the file on disk predates the version:/patterns: wrapper, and
        # therefore records config/-relative file keys. See load().
        self.legacy = False
        if path.exists():
            self.load()

    def load(self) -> None:
        """Read the lock, refusing anything this ibek cannot read faithfully.

        A pre-wrapper lock's top level *is* ``{pattern_name: entry}``. It is read
        as such and flagged :attr:`legacy`, **not** rejected: the recovery from an
        old lock is ``ibek pattern update``, so update / restore / add must all be
        able to open one — a hard error here would make the only documented escape
        route impossible to run.

        What must never happen is reading one as an *empty* lock, which would let
        ``check`` pass having verified nothing: a failure that looks like success
        in a CI log. Every entry is therefore carried over verbatim, and its
        config/-relative keys are left exactly as written so ``check`` can
        recognise them and name the command that rewrites them.
        """
        try:
            raw = YAML(typ="safe").load(self.path) or {}
        except YAMLError as exc:
            raise PatternError(f"{self.path}: invalid YAML: {exc}") from exc
        if not isinstance(raw, dict):
            raise PatternError(f"{self.path}: expected a mapping at the top level")
        if "patterns" in raw or isinstance(raw.get("version"), int):
            # Wrapped: a root ``version:`` is an int and pattern names are not,
            # so the two shapes cannot be confused for one another.
            version = raw.get("version")
            if version not in SUPPORTED_LOCK_VERSIONS:
                supported = ", ".join(str(v) for v in sorted(SUPPORTED_LOCK_VERSIONS))
                raise PatternError(
                    f"{self.path}: unsupported lock version {version!r} "
                    f"(this ibek reads: {supported})"
                )
            patterns = raw.get("patterns") or {}
        else:
            self.legacy = True
            patterns = raw
        if not isinstance(patterns, dict):
            raise PatternError(f"{self.path}: 'patterns' must be a mapping")
        try:
            self.patterns = {
                name: PatternEntry(**entry) for name, entry in patterns.items()
            }
        except (TypeError, ValidationError) as exc:
            raise PatternError(f"{self.path}: invalid pattern entry: {exc}") from exc

    def vendored_keys(self, name: str) -> set[str]:
        """A pattern's recorded files as **destination-root-relative** paths.

        Rebasing a legacy lock's config/-relative keys here rather than at load
        time is deliberate: ``check`` needs to see the keys exactly as written in
        order to recognise an old lock, while orphan pruning needs to know where
        the files actually are, or ``update`` would strand every file the new
        file-set no longer produces.
        """
        prefix = "config/" if self.legacy else ""
        return {prefix + key for key in self.patterns[name].files}

    def set_pattern(
        self, name: str, version: str, source: str, files: dict[str, str]
    ) -> None:
        self.patterns[name] = PatternEntry(version=version, source=source, files=files)

    def remove_pattern(self, name: str) -> None:
        self.patterns.pop(name, None)

    def save(self) -> None:
        # Whatever shape it was read in, what is written is the current format.
        self.legacy = False
        # Patterns are emitted in name order so a lock re-written with the same
        # set in a different order produces no diff.
        data = {
            "version": LOCK_VERSION,
            "patterns": {
                name: {
                    "version": self.patterns[name].version,
                    "source": self.patterns[name].source,
                    "files": dict(self.patterns[name].files),
                }
                for name in sorted(self.patterns)
            },
        }
        yaml = YAML()
        yaml.default_flow_style = False
        # Keep each "<file>: sha256:<hex>" on one line (do not wrap long hashes).
        yaml.width = 4096
        if not self.patterns:
            # An empty lock is removed rather than left as an empty document.
            if self.path.exists():
                self.path.unlink()
            return
        stream = StringIO()
        yaml.dump(data, stream)
        self.path.write_text(stream.getvalue())
