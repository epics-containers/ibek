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


def is_recognised(raw: object) -> bool:
    """True if ``raw`` is already the ``version:`` / ``patterns:`` shape."""
    return isinstance(raw, dict) and (
        "patterns" in raw or isinstance(raw.get("version"), int)
    )


def rebase_files(files: dict[str, str]) -> dict[str, str]:
    """Prefix every key with ``config/``, the root every such key was relative
    to, unless it is already there."""
    return {
        (key if key.startswith("config/") else f"config/{key}"): value
        for key, value in files.items()
    }


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
