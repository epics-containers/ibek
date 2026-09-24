#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml"]
# ///
"""
Converts a flat ``runtime-lock.yaml`` to the format ibek reads.

ibek's ``version: 1`` / ``patterns:`` layout is a single mapping keyed by
pattern name, each entry's ``files`` keyed by a path relative to the
destination root (e.g. ``config/mydevice.proto``). A lock written with pattern
names directly at the top level, and ``files`` keys relative to ``config/``
instead, is a different shape: this script rewrites it in place into the one
ibek reads, without touching the vendored files or their recorded hashes.

Usage:

    uv run scripts/convert-runtime-lock.py <path/to/runtime-lock.yaml>

Standalone: it carries its own dependency (PEP 723 inline metadata), so it
runs the same way from inside a services repo as from an ibek checkout, and it
is not part of the installed ibek package.
"""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

LOCK_VERSION = 1


def is_recognised(raw: dict) -> bool:
    """True if ``raw`` is already the fully-formed ``version:``/``patterns:``
    shape ibek reads, so there is nothing to convert."""
    return raw.get("version") == LOCK_VERSION and isinstance(raw.get("patterns"), dict)


def is_malformed_wrapper(raw: dict) -> bool:
    """True if ``raw`` carries a ``version`` or ``patterns`` key but not the
    exact shape ``is_recognised`` requires.

    Such a lock is a broken wrapper, not a flat lock that simply has not been
    converted yet, so it must not be handed to :func:`convert` as if it were
    one -- doing so would silently misread its keys as pattern names.
    """
    return "version" in raw or "patterns" in raw


def rebase_files(files: dict[str, str]) -> dict[str, str]:
    """Prefix every key with ``config/``, the root every such key was relative
    to. A flat lock's keys are always ``config/``-relative, even one that
    happens to start with ``config/`` itself (a pattern vendoring its own
    nested ``config/`` folder) — so the prefix is unconditional."""
    return {f"config/{key}": value for key, value in files.items()}


def convert(raw: dict) -> dict:
    """Return ``raw`` (a flat ``{pattern: entry}`` mapping) as the wrapped
    shape."""
    patterns = {}
    for name in sorted(raw):
        entry = dict(raw[name])
        if "files" in entry:
            entry["files"] = rebase_files(entry["files"])
        patterns[name] = entry
    return {"version": LOCK_VERSION, "patterns": patterns}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(
            "usage: uv run scripts/convert-runtime-lock.py <runtime-lock.yaml>",
            file=sys.stderr,
        )
        return 2
    path = Path(argv[0])
    if not path.is_file():
        print(f"{path}: no such file", file=sys.stderr)
        return 1

    yaml = YAML()
    try:
        raw = yaml.load(path) or {}
    except YAMLError as exc:
        print(f"{path}: invalid YAML: {exc}", file=sys.stderr)
        return 1
    if not isinstance(raw, dict):
        print(f"{path}: expected a mapping at the top level", file=sys.stderr)
        return 1

    if is_recognised(raw):
        print(f"{path}: already in the format ibek reads; nothing to do")
        return 0
    if is_malformed_wrapper(raw):
        print(
            f"{path}: has 'version' and/or 'patterns' but not the shape ibek "
            f"reads ('version' must be {LOCK_VERSION}, 'patterns' must be a "
            "mapping)",
            file=sys.stderr,
        )
        return 1

    try:
        converted = convert(raw)
    except (AttributeError, TypeError) as exc:
        print(f"{path}: not a pattern lock: {exc}", file=sys.stderr)
        return 1

    yaml.default_flow_style = False
    yaml.width = 4096
    stream = StringIO()
    yaml.dump(converted, stream)
    path.write_text(stream.getvalue())

    names = ", ".join(sorted(converted["patterns"]))
    print(f"{path}: converted {len(converted['patterns'])} pattern(s): {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
