import shutil
import subprocess
from pathlib import Path
from typing import List

import typer

from ibek.globals import IOC_FOLDER, SYMLINKS


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
    Find all the runtime assets in an EPICS installation and copy them to a
    new folder hierarchy for packaging into a container runtime stage.

    This should be performed in a throw away container stage (runtime_prep)
    as it is destructive of the source folder, because it uses move for speed.
    """
    asset_matches = "bin|configure|db|dbd|include|lib|template|config|*.sh"

    just_copy = (
        [
            source / "support" / "configure",
            SYMLINKS,
            IOC_FOLDER,
            Path("/venv"),
        ]
        if defaults
        else []
    )

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

    extra_files = just_copy + extras
    for asset in extra_files:
        src = source / asset
        if src.exists():
            dest_file = destination / asset.relative_to("/")
            move_file(src, dest_file, binary)
        else:
            raise RuntimeError(f"extra runtime asset {src} missing")
