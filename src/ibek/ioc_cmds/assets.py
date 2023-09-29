import shutil
import subprocess
from pathlib import Path
from typing import List

import typer

from ibek.globals import EPICS_ROOT, IOC_FOLDER, SYMLINKS


def get_ioc_src():
    """
    The generic ioc source folder is mounted into the container at
    /epics/ioc-XXXXX and should always contain the ibek-support
    submodule. Therefore we can find the ibek-support folder by looking
    for the ibek-support folder.

    Functions that use this should provide an override variable that allows
    the ibek caller to specify the location.
    """
    try:
        ibek_support = list(EPICS_ROOT.glob("*/ibek-support"))[0]
    except IndexError:
        raise RuntimeError(
            f"Could not find ibek-support in {EPICS_ROOT}."
            "ibek should be run from inside a container with"
            "a generic ioc source folder mounted at /epics/ioc-XXXXX"
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
    extract and copy runtime assets
    """
    asset_matches = "bin|configure|db|dbd|include|lib|template|config|*.sh"

    ibek_support = get_ioc_src()

    just_copy = (
        [
            ibek_support,
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
