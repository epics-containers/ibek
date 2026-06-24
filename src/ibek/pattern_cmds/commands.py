"""
``ibek pattern`` — vendor runtime-support patterns into a services repo.

Patterns (StreamDevice device support, AreaDetector plugin sets, ...) are copied
from a central library into an IOC instance at a pinned version, recorded in a
``runtime-lock.yaml`` with per-file SHA-256 integrity hashes. This restores a
per-instance version axis independent of the image, and makes "what is this IOC
running?" answerable from the committed lock with cryptographic certainty.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

import typer

from ibek.globals import NaturalOrderGroup

from . import vendor
from .schema import generate_instance_schema
from .sources import PatternError

log = logging.getLogger(__name__)
pattern_cli = typer.Typer(cls=NaturalOrderGroup)

InstanceArg = Annotated[
    Path,
    typer.Argument(
        help="The IOC instance folder (containing config/)",
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
    instance: InstanceArg = Path("."),
    source: SourceOpt = None,
):
    """Vendor a pattern into an instance, writing files + runtime-lock.yaml + schema."""
    try:
        vendor.add(name, instance, source_override=source)
    except PatternError as exc:
        _fail(exc)
    typer.echo(f"vendored {name} into {instance}")


@pattern_cli.command()
def update(
    name: Annotated[
        str | None,
        typer.Argument(help="Pattern name to update (default: all in the lock)"),
    ] = None,
    instance: InstanceArg = Path("."),
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help="New pinned version to vendor"),
    ] = None,
    source: SourceOpt = None,
):
    """Re-vendor a pattern to a new pinned version; refresh hashes + schema."""
    try:
        vendor.update(name, instance, version=version, source_override=source)
    except PatternError as exc:
        _fail(exc)
    typer.echo(f"updated {name or 'all patterns'} in {instance}")


@pattern_cli.command()
def check(
    instance: InstanceArg = Path("."),
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
    result = vendor.check(instance, allow_dirty=allow)
    for warning in result.warnings:
        typer.echo(f"warning: {warning}")
    for failure in result.failures:
        typer.echo(f"error: {failure}", err=True)
    if not result.ok:
        raise typer.Exit(1)
    typer.echo(f"{instance}: vendored files match the lock")


@pattern_cli.command()
def restore(
    name: Annotated[
        str | None,
        typer.Argument(help="Pattern name to restore (default: all in the lock)"),
    ] = None,
    instance: InstanceArg = Path("."),
):
    """Revert vendored files to the version pinned in runtime-lock.yaml."""
    try:
        vendor.restore(name, instance)
    except PatternError as exc:
        _fail(exc)
    typer.echo(f"restored {name or 'all patterns'} in {instance}")


@pattern_cli.command()
def schema(
    instance: InstanceArg = Path("."),
):
    """Generate the instance's ioc.schema.json and rewrite ioc.yaml's header.

    Fetches the published base schema for the instance's pinned image and merges
    the instance's vendored / local support entities into it.
    """
    generate_instance_schema(instance)
