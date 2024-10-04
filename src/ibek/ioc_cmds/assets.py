import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import List

import typer

from ibek.globals import GLOBALS

log = logging.getLogger(__name__)


def move_file(src: Path, dest: Path, binary: List[str]):
    """
    Move a file / tree / symlink from src to dest, stripping symbols from
    binaries if they are in the binary list.
    """
    dest.parent.mkdir(exist_ok=True, parents=True)

    if src.is_symlink():
        # copy the symlink
        shutil.rmtree(dest, ignore_errors=True)
        dest = dest.parent
        typer.echo(f"Symlink {src} to {dest}")
        shutil.copy(src, dest, follow_symlinks=False)
    else:
        typer.echo(f"Moving {src} to {dest}")
        if subprocess.call(["bash", "-c", f"mv {src} {dest}"]) > 0:
            raise RuntimeError(f"Failed to move {src} to {dest}")
    if dest.name in binary:
        # strip the symbols from the binary
        cmd = f"strip $(find {dest} -type f) &> /dev/null"
        subprocess.call(["bash", "-c", cmd])


def extract_assets(
    destination: Path,
    source: Path,
    extras: List[Path],
    defaults: bool,
    dry_run: bool = False,
):
    """
    extract and copy runtime assets from a completed developer stage container
    """

    if GLOBALS.STATIC_BUILD:
        # static builds only need database and .proto files from support modules
        asset_matches = "db|*/protocol"
    else:
        # dynamically linked builds need binaries and protocol files
        asset_matches = "bin|db|lib|*/protocol"

    # chdir out of the folders we will move
    os.chdir(source)

    # a default set of assets that all IOCs will need at runtime
    if defaults:
        default_assets = [
            source / "support" / "configure",
            GLOBALS.PVI_DEFS,
            GLOBALS.IBEK_DEFS,
            GLOBALS.IOC_FOLDER,  # get the IOC folder symlink
            Path.readlink(
                GLOBALS.IOC_FOLDER
            ).parent,  # get contents of IOC folder and its source (parent)
            GLOBALS.EPICS_ROOT.parent / "venv",  # virtualenv is a peer to /epics
        ]
    else:
        default_assets = []

    # folder names with useful files in them
    useful_files = ["bin", "lib", "db"]

    # get the list of additional files supplied by add_runtime_files
    if GLOBALS.RUNTIME_FILES.exists():
        with GLOBALS.RUNTIME_FILES.open("r") as f:
            runtime_files = [Path(line.strip()) for line in f.readlines()]
    else:
        runtime_files = []

    # move the default assets and extras in their entirety
    extra_files = default_assets + extras + runtime_files
    for asset in extra_files:
        src = source / asset
        if src.exists():
            dest_file = destination / asset.relative_to("/")
            if dry_run:
                typer.echo(
                    f"Would move extra asset {src} to {dest_file} with {useful_files}"
                )
            else:
                move_file(src, dest_file, useful_files)
        else:
            typer.echo(f"WARNING: runtime asset {src} missing")

    # identify EPICS modules as folders with binary output folders
    # and move only their output folders as specified by asset_matches
    binaries: List[Path] = []
    for find in useful_files:
        # only look two levels deep
        binaries.extend(source.glob(f"*/*/{find}"))
        binaries.extend(source.glob(f"*/{find}"))

    modules = [binary.parent for binary in binaries]

    destination.mkdir(exist_ok=True, parents=True)
    for module in modules:
        # make sure dest folder exists
        destination_module = destination / module.relative_to("/")

        # use globs to make a list of the things we want to copy
        asset_globs = [module.glob(match) for match in asset_matches.split("|")]
        assets: List[Path] = [
            asset for asset_glob in asset_globs for asset in asset_glob
        ]

        for asset in assets:
            src = module / asset
            if src.exists():
                dest_file = destination_module / asset.relative_to(module)
                if dry_run:
                    typer.echo(f"Would move {src} to {dest_file} with {useful_files}")
                else:
                    move_file(src, dest_file, useful_files)
