import os
import shutil
import subprocess
from pathlib import Path
from typing import List

import typer

from ibek.globals import EPICS_ROOT, IBEK_DEFS, IOC_FOLDER, PVI_DEFS


def get_ioc_source() -> Path:
    """
    The generic ioc source folder is mounted into the container at
    /epics/ioc-XXXXX and should always contain the ibek-support
    submodule. Therefore we can find the ibek-support folder by looking
    for the ibek-support folder.

    Functions that use this should provide an override variable that allows
    the ibek caller to specify the location.
    """
    try:
        ibek_support = (
            list(EPICS_ROOT.glob("*/ibek-support"))
            or list(Path("..").glob("/**/ibek-support"))
        )[0]
    except IndexError:
        raise RuntimeError(
            "Could NOT find a suitable location for the IOC source folder. "
            "ibek must be run in a container with the generic IOC source folder"
        )
    return (ibek_support / "..").resolve()


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


def extract_assets(destination: Path, source: Path, extras: List[Path], defaults: bool):
    """
    extract and copy runtime assets from a completed developer stage container
    """
    asset_matches = "bin|configure|db|dbd|include|lib|template|config|*.sh"

    # chdir out of the folders we will move
    os.chdir(source)

    # a default set of assets that all IOCs will need at runtime
    if defaults:
        default_assets = [
            get_ioc_source() / "ibek-support",
            source / "support" / "configure",
            PVI_DEFS,
            IBEK_DEFS,
            IOC_FOLDER,
            Path("/venv"),
        ]
    else:
        default_assets = []

    # identify EPICS modules as folders with binary output folders
    binary = ["bin", "lib"]

    binaries: List[Path] = []
    for find in binary:
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
                move_file(src, dest_file, binary)

    extra_files = default_assets + extras
    for asset in extra_files:
        src = source / asset
        if src.exists():
            dest_file = destination / asset.relative_to("/")
            move_file(src, dest_file, binary)
        else:
            raise RuntimeError(f"extra runtime asset {src} missing")
