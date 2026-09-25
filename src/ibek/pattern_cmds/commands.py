"""
``ibek pattern`` — vendor runtime-support patterns into a services repo.

Patterns (StreamDevice device support, AreaDetector plugin sets, ...) are copied
from a central library into a destination folder — normally an IOC instance — at
a pinned version, recorded in a ``runtime-lock.yaml`` with per-file SHA-256
integrity hashes. Which files are copied and where they land is declared by the
pattern's ``ibek.manifest.yaml``. This restores a per-instance version axis
independent of the image, and makes "what is this IOC running?" answerable from
the committed lock with cryptographic certainty.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

import typer

from ibek.globals import NaturalOrderGroup

from . import vendor
from .lock import Selection, SelectRule
from .schema import generate_instance_schema, is_instance
from .sources import PatternError

log = logging.getLogger(__name__)
pattern_cli = typer.Typer(cls=NaturalOrderGroup)

DestArg = Annotated[
    Path,
    typer.Argument(
        help="The destination folder to vendor into (an IOC instance root)",
        exists=True,
        dir_okay=True,
        file_okay=False,
        autocompletion=lambda: [],
        resolve_path=True,
    ),
]

SourceOpt = Annotated[
    str | None,
    typer.Option(
        "--source",
        "-s",
        help="Override the library source URI (git URL or local path)",
    ),
]

NameOpt = Annotated[
    str | None,
    typer.Option(
        "--name",
        "-n",
        help="Restrict to a single pattern by name (default: all in the lock)",
    ),
]


def _selection(include: list[str], exclude: list[str]) -> Selection | None:
    """Build a ``select:`` from ``--include SRC=DEST`` / ``--exclude SRC`` options.

    ``SRC=DEST`` is split at its last ``=``: a regex may contain ``=`` (``(?=``),
    a destination path does not.
    """
    rules = []
    for text in include:
        src, sep, dest = text.rpartition("=")
        if not sep or not src or not dest:
            raise PatternError(f"--include {text!r}: expected SRC=DEST")
        rules.append(SelectRule(src=src, dest=dest))
    if not rules and not exclude:
        return None
    return Selection(include=rules, exclude=exclude)


def _fail(exc: Exception) -> None:
    log.error(str(exc))
    raise typer.Exit(1) from exc


@pattern_cli.command()
def add(
    name: Annotated[
        str,
        typer.Argument(
            help="Pattern reference: [library:]name[@version], "
            "e.g. ibek-runtime-streamdevice:lakeshore340@1.0.0",
        ),
    ],
    dest: DestArg = Path("."),
    source: SourceOpt = None,
    include: Annotated[
        list[str] | None,
        typer.Option(
            "--include",
            help="Also vendor pattern files matching the regex SRC, to DEST "
            "(a manifest-style dest). Given as SRC=DEST; repeatable; "
            "recorded in runtime-lock.yaml",
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude",
            help="Do not vendor manifest files matching this regex; repeatable; "
            "recorded in runtime-lock.yaml",
        ),
    ] = None,
):
    """Vendor a pattern into a destination: files + runtime-lock.yaml + schema."""
    try:
        select = _selection(include or [], exclude or [])
        vendor.add(name, dest, source_override=source, select=select)
    except PatternError as exc:
        _fail(exc)
    typer.echo(f"vendored {name} into {dest}")


@pattern_cli.command()
def update(
    dest: DestArg = Path("."),
    name: NameOpt = None,
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help="New pinned version to vendor"),
    ] = None,
    source: SourceOpt = None,
):
    """Re-vendor a pattern to a new pinned version; refresh hashes + schema."""
    try:
        vendor.update(name, dest, version=version, source_override=source)
    except PatternError as exc:
        _fail(exc)
    typer.echo(f"updated {name or 'all patterns'} in {dest}")


@pattern_cli.command()
def check(
    dest: DestArg = Path("."),
    allow_dirty: Annotated[
        bool,
        typer.Option(
            "--allow-dirty",
            help="Downgrade hash mismatches to warnings "
            "(also enabled by IBEK_ALLOW_DIRTY=1)",
        ),
    ] = False,
):
    """Verify vendored files match runtime-lock.yaml (vendor integrity)."""
    allow = allow_dirty or os.getenv("IBEK_ALLOW_DIRTY") == "1"
    result = vendor.check(dest, allow_dirty=allow)
    for warning in result.warnings:
        typer.echo(f"warning: {warning}")
    for failure in result.failures:
        typer.echo(f"error: {failure}", err=True)
    if not result.ok:
        raise typer.Exit(1)
    typer.echo(f"{dest}: vendored files match the lock")


@pattern_cli.command()
def restore(
    dest: DestArg = Path("."),
    name: NameOpt = None,
):
    """Revert vendored files to the version pinned in runtime-lock.yaml."""
    try:
        vendor.restore(name, dest)
    except PatternError as exc:
        _fail(exc)
    typer.echo(f"restored {name or 'all patterns'} in {dest}")


@pattern_cli.command()
def schema(
    dest: DestArg = Path("."),
):
    """Generate the instance's ioc.schema.json and rewrite ioc.yaml's header.

    Fetches the published base schema for the instance's pinned image and merges
    the instance's vendored / local support entities into it.
    """
    # `add` is deliberately silent about a destination that is not an instance;
    # this command is not. Asking for a schema and getting no output at all is
    # indistinguishable from success.
    if not is_instance(dest):
        typer.echo(
            f"{dest} is not an IOC instance: no values.yaml / compose.yml pinning "
            "an image, so there is no schema to generate"
        )
        return
    try:
        generate_instance_schema(dest)
    except PatternError as exc:
        _fail(exc)
