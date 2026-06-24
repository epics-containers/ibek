"""
Multi-library source resolution and fetching for ``ibek pattern``.

A pattern name may be qualified with the library it lives in, e.g.
``ibek-runtime-support:detectorPlugins@1.0.0``. Libraries resolve to a source —
either a git URL (cloned at the pinned tag) or a local directory (used as-is,
handy for tests and for vendoring from an un-tagged working copy).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# The central pattern libraries known to ibek out of the box. Either may be
# overridden, and further libraries added, via the IBEK_PATTERN_LIBRARIES
# environment variable ("name=uri,name2=uri2").
DEFAULT_LIBRARIES: dict[str, str] = {
    "ibek-runtime-streamdevice": (
        "https://github.com/epics-containers/ibek-runtime-streamdevice"
    ),
    "ibek-runtime-support": (
        "https://github.com/epics-containers/ibek-runtime-support"
    ),
}

_QUALIFIED_RE = re.compile(
    r"^(?:(?P<library>[^:@]+):)?(?P<name>[^:@]+)(?:@(?P<version>.+))?$"
)


class PatternError(Exception):
    """A user-facing pattern resolution / fetch error."""


@dataclass
class PatternRef:
    """A parsed ``[library:]name[@version]`` reference."""

    name: str
    library: str | None = None
    version: str | None = None


def parse_ref(qualified: str) -> PatternRef:
    """Parse a ``[library:]name[@version]`` string."""
    match = _QUALIFIED_RE.match(qualified.strip())
    if not match:
        raise PatternError(f"invalid pattern reference: {qualified!r}")
    return PatternRef(
        name=match["name"],
        library=match["library"],
        version=match["version"],
    )


def library_registry(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return the library->source registry (defaults + env + ``extra``)."""
    registry = dict(DEFAULT_LIBRARIES)
    env = os.getenv("IBEK_PATTERN_LIBRARIES", "")
    for item in (piece for piece in env.split(",") if piece.strip()):
        name, _, uri = item.partition("=")
        if uri:
            registry[name.strip()] = uri.strip()
    if extra:
        registry.update(extra)
    return registry


def source_label(uri: str) -> str:
    """Normalise a source URI to the stable label recorded in the lock."""
    label = re.sub(r"^https?://", "", uri)
    label = re.sub(r"\.git$", "", label)
    return label.rstrip("/")


def _is_local(uri: str) -> bool:
    if uri.startswith("file://"):
        return True
    if re.match(r"^[a-z]+://", uri):
        return False
    return Path(uri).exists()


def _local_path(uri: str) -> Path:
    return Path(uri[len("file://") :] if uri.startswith("file://") else uri)


def _clone_pattern(uri: str, name: str, version: str | None, dest: Path) -> Path:
    """Clone ``uri`` at ``version`` and return the ``name`` pattern folder."""
    clone_dir = dest / "clone"
    cmd = ["git", "clone", "--depth", "1", "--quiet"]
    if version:
        cmd += ["--branch", version]
    # ``--`` terminates option parsing so a uri/path beginning with ``-`` (from
    # IBEK_PATTERN_LIBRARIES, --source, or a lock label) cannot be read as a flag.
    cmd += ["--", uri, str(clone_dir)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise PatternError(
            f"failed to clone {uri}@{version or 'HEAD'}: {result.stderr.strip()}"
        )
    pattern_dir = clone_dir / name
    if not pattern_dir.is_dir():
        raise PatternError(
            f"pattern {name!r} not found in {source_label(uri)}@{version or 'HEAD'}"
        )
    return pattern_dir


def fetch_pattern(uri: str, name: str, version: str | None, dest: Path) -> Path:
    """Materialise the ``name`` pattern folder from ``uri`` into ``dest``.

    Returns the path to the folder holding the pattern's file-set.
    """
    if _is_local(uri):
        pattern_dir = _local_path(uri) / name
        if not pattern_dir.is_dir():
            raise PatternError(f"pattern {name!r} not found in local library {uri}")
        # Copy so the caller always works against a private, stable tree.
        staged = dest / name
        shutil.copytree(pattern_dir, staged)
        return staged
    return _clone_pattern(uri, name, version, dest)


def resolve_source(
    ref: PatternRef,
    source_override: str | None = None,
    extra_libraries: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
    """Resolve a reference to ``(source_uri, candidate_libraries)``.

    If the reference names a library (or ``source_override`` is given) the source
    is unambiguous. Otherwise every registered library is returned as a candidate
    to be probed in order by the caller.
    """
    if source_override:
        return source_override, [ref.library or ref.name]
    registry = library_registry(extra_libraries)
    if ref.library:
        if ref.library not in registry:
            raise PatternError(
                f"unknown library {ref.library!r}; "
                f"known: {', '.join(sorted(registry)) or '(none)'}"
            )
        return registry[ref.library], [ref.library]
    if not registry:
        raise PatternError("no pattern libraries configured")
    # Unqualified: caller probes each library in registry order.
    return "", list(registry)
