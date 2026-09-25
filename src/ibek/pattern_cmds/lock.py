"""
The ``runtime-lock.yaml`` integrity lock for vendored runtime-support patterns.

A pattern is an arbitrary file-set (``*.ibek.support.yaml`` plus optional
proto / template / db / req / ...) vendored from a central library at a pinned
version. Vendored files are byte-identical to the library at its tag — nothing
is injected or rewritten on the way in — so the recorded SHA-256 covers the
upstream bytes verbatim and ``ibek pattern check`` is a trivial
``sha256(file) == lock``.

Keys under a pattern's ``files`` are relative to the **destination root**, not to
``config/``. A pattern with no manifest is vendored through a synthesised
default that lands everything under ``config/``, so those keys read
``config/...`` naturally — there is no per-pattern base field and no branch in
``check``.

The lock is a single mapping under a ``version:`` / ``patterns:`` root. A file
in any other shape is refused with a generic error naming the standalone
conversion script — see :data:`UNRECOGNISED_LOCK_HINT`.

A pattern entry may carry a ``select:`` that adjusts the manifest's file-set for
this destination: ``include`` rules vendor further files (or route a file to a
different destination), ``exclude`` regexes drop files the manifest would
vendor. The file is written as ``version: 1`` when no pattern has a selection
and ``version: 2`` when any does, so a reader that predates ``select:`` refuses
a lock that uses it with "unsupported lock version" instead of vendoring a
different file-set from the one recorded.
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
# is deliberately *not* a switch ibek branches on to convert what it reads (see
# ADR 0005). Version 2 is version 1 plus the per-pattern ``select:``; the version
# written is the lowest one that can hold the lock's content, so a lock without
# a selection stays readable by every ibek that reads version 1.
LOCK_VERSION = 1
SELECT_LOCK_VERSION = 2
SUPPORTED_LOCK_VERSIONS = frozenset({LOCK_VERSION, SELECT_LOCK_VERSION})
LOCK_KEYS = ("version", "patterns")

# A lock entry whose hash is replaced by a string starting with this marker is a
# deliberately, visibly dirty file (e.g. testing a fix against real hardware).
DIRTY_MARKER = "DIRTY"

# Emitted whenever a lock's top level is not ``{"version": int, "patterns":
# {...}}``. Deliberately silent about what shape it actually is: the only
# actionable fact is "convert it", and that stays true however the format goes
# on to change.
UNRECOGNISED_LOCK_HINT = (
    "lock format not recognised; convert it with "
    "'uv run scripts/convert-runtime-lock.py <lock>' from an ibek checkout, or "
    "'uv run https://raw.githubusercontent.com/epics-containers/ibek/main/"
    "scripts/convert-runtime-lock.py <lock>' from anywhere, including a "
    "services repo with no ibek checkout "
    "(see docs/how-to/vendor-runtime-patterns.md)"
)


def file_hash(data: bytes) -> str:
    """Return the ``sha256:<hex>`` digest of ``data``."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def is_dirty(value: str) -> bool:
    """True if a lock file-entry value is a deliberate DIRTY marker."""
    return value.strip().startswith(DIRTY_MARKER)


class SelectRule(BaseSettings):
    """One ``select.include`` rule: the same ``src`` / ``dest`` as a manifest rule."""

    src: str
    dest: str


class Selection(BaseSettings):
    """A destination's adjustment to a pattern's manifest.

    ``include`` rules are tried first, in order, and a file one of them matches
    is vendored where that rule says, whatever the manifest says about it.
    ``exclude`` regexes drop files that would otherwise be vendored by the
    manifest. Both match the pattern-relative path with ``re.fullmatch``, like
    the manifest's ``src``.
    """

    include: list[SelectRule] = []
    exclude: list[str] = []

    def is_empty(self) -> bool:
        return not self.include and not self.exclude


class PatternEntry(BaseSettings):
    """One vendored pattern's lock record."""

    version: str
    source: str
    select: Selection | None = None
    files: dict[str, str]


class RuntimeLock:
    """Read/modify/write a ``runtime-lock.yaml`` at a destination root."""

    def __init__(self, path: Path):
        self.path = path
        self.patterns: dict[str, PatternEntry] = {}
        if path.exists():
            self.load()

    def load(self) -> None:
        """Read the lock, refusing any shape but ``version:`` / ``patterns:``.

        A shape this ibek does not recognise is refused outright, with a
        generic hint naming the standalone conversion script: there is no safe
        way to guess a file-set from an unrecognised shape, and reading one as
        an *empty* lock would let ``check`` pass having verified nothing.

        An empty file (or one containing only ``{}``) carries no shape to
        judge either way, so it is read the same as a missing lock: no
        patterns, nothing to check.
        """
        try:
            raw = YAML(typ="safe").load(self.path) or {}
        except YAMLError as exc:
            raise PatternError(f"{self.path}: invalid YAML: {exc}") from exc
        if not isinstance(raw, dict):
            raise PatternError(f"{self.path}: expected a mapping at the top level")
        if not raw:
            return
        if "patterns" not in raw and not isinstance(raw.get("version"), int):
            raise PatternError(f"{self.path}: {UNRECOGNISED_LOCK_HINT}")
        version = raw.get("version")
        if version not in SUPPORTED_LOCK_VERSIONS:
            supported = ", ".join(str(v) for v in sorted(SUPPORTED_LOCK_VERSIONS))
            raise PatternError(
                f"{self.path}: unsupported lock version {version!r} "
                f"(this ibek reads: {supported})"
            )
        # A key this ibek does not know would be ignored here and then dropped
        # by the next save, losing whatever it recorded without a word.
        unknown = sorted(str(key) for key in raw if key not in LOCK_KEYS)
        if unknown:
            raise PatternError(
                f"{self.path}: unknown top-level key(s) {', '.join(unknown)} "
                f"(a lock holds only {' and '.join(LOCK_KEYS)})"
            )
        patterns = raw.get("patterns") or {}
        if not isinstance(patterns, dict):
            raise PatternError(f"{self.path}: 'patterns' must be a mapping")
        try:
            self.patterns = {
                name: PatternEntry(**entry) for name, entry in patterns.items()
            }
        except (TypeError, ValidationError) as exc:
            raise PatternError(f"{self.path}: invalid pattern entry: {exc}") from exc
        for name, entry in self.patterns.items():
            if entry.select is not None and entry.select.is_empty():
                entry.select = None
            if entry.select is not None and version < SELECT_LOCK_VERSION:
                raise PatternError(
                    f"{self.path}: pattern {name!r} has a 'select' but the lock "
                    f"is version {version}; a lock with a selection is version "
                    f"{SELECT_LOCK_VERSION}, so that an ibek which cannot apply "
                    "it refuses the lock"
                )

    def vendored_keys(self, name: str) -> set[str]:
        """A pattern's recorded files as destination-root-relative paths."""
        return set(self.patterns[name].files)

    def set_pattern(
        self,
        name: str,
        version: str,
        source: str,
        files: dict[str, str],
        select: Selection | None = None,
    ) -> None:
        if select is not None and select.is_empty():
            select = None
        self.patterns[name] = PatternEntry(
            version=version, source=source, select=select, files=files
        )

    def remove_pattern(self, name: str) -> None:
        self.patterns.pop(name, None)

    def _entry_data(self, name: str) -> dict:
        """One pattern's mapping, in the order it is written.

        ``select`` sits between ``source`` and ``files`` and is left out when
        there is no selection, so a lock without one is written exactly as a
        version 1 lock always has been.
        """
        entry = self.patterns[name]
        data: dict = {"version": entry.version, "source": entry.source}
        if entry.select is not None:
            select: dict = {}
            if entry.select.include:
                select["include"] = [
                    {"src": rule.src, "dest": rule.dest}
                    for rule in entry.select.include
                ]
            if entry.select.exclude:
                select["exclude"] = list(entry.select.exclude)
            data["select"] = select
        data["files"] = dict(entry.files)
        return data

    def save(self) -> None:
        # Patterns are emitted in name order so a lock re-written with the same
        # set in a different order produces no diff.
        has_select = any(entry.select for entry in self.patterns.values())
        data = {
            "version": SELECT_LOCK_VERSION if has_select else LOCK_VERSION,
            "patterns": {
                name: self._entry_data(name) for name in sorted(self.patterns)
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
