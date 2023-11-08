"""
Functions for inserting snippets into files in an idempotent fashion
"""

from enum import Enum
from pathlib import Path
from typing import List

import typer

from ibek.globals import SUPPORT


class Local(str, Enum):
    non_local = ""
    local = ".local"


class Arch(str, Enum):
    none = ""
    common = ".Common"
    x86_64 = ".linux-x86_64"
    arm64 = ".linux-arm64"
    vxWorks = ".vxWorks-ppc604_long"
    rtems = ".RTEMS-beatnik"


def get_config_site_file(
    module: str,
    host: Arch = Arch.x86_64,
    target: Arch = Arch.common,
) -> Path:
    """
    Return the path to an CONFIG_SITE file for a support module.
    Default is /epics/module/configure/CONFIG_SITE.local.linux-x86_64.Common
    """
    name = f"CONFIG_SITE{host.value}{target.value}"
    filepath = SUPPORT / module / "configure" / name

    return filepath


def get_release_file(
    module: str,
    host: Arch = Arch.none,
    target: Arch = Arch.none,
    local: Local = Local.local,
) -> Path:
    """
    Return the path to an EPICS RELEASE file for a support
    default is /epics/module/configure/RELEASE.local
    """
    name = f"RELEASE{host.value}{target.value}{local.value}"
    filepath = SUPPORT / module / "configure" / name

    return filepath


def add_list_to_file(file: Path, text_list: List[str]):
    """
    add a sequence of strings into a file, leaving previously existing
    strings where they are
    """
    if len(text_list) == 0:
        return

    for line in text_list:
        # skip blanks and comments
        if line.startswith("#") or line == "":
            continue
        add_text_once(file, line)


def add_text_once(file: Path, text: str):
    """
    Idempotent add of text to a file.
    Creates the file if it doesn't exist.
    """

    if not file.exists():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text + "\n")
    else:
        current = file.read_text()
        if text not in current:
            file.write_text(current + text + "\n")


def symlink_files(source_directory: Path, file_pattern: str, target_directory: Path):
    """Symlink files patching the given pattern in source directory to target directory.

    Args:
        source_directory: Directory containing source files
        file_patterm: Pattern of files in source directory to be symlinked
        target_directory: Directory to create symlinks in

    """
    typer.echo(
        f"Symlinking {file_pattern} from {source_directory} to {target_directory}:"
    )
    target_directory.mkdir(parents=True, exist_ok=True)
    for yaml in source_directory.glob(file_pattern):
        typer.echo(f" {target_directory / yaml.name} -> {yaml}")
        target = target_directory / yaml.name
        target.unlink(missing_ok=True)
        target.symlink_to(yaml)
