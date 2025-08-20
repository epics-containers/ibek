import os
import re
import subprocess
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from ibek.globals import (
    GLOBALS,
    NaturalOrderGroup,
)
from ibek.support import Support


class AptWhen(str, Enum):
    dev = "dev"
    run = "run"
    both = "both"


# find macro name and macro value in a RELEASE file
# only include values with at least one / (attempt to match filepaths only)
PARSE_MACROS = re.compile(r"^([A-Z_a-z0-9]*)\s*=\s*(.*/.*)$", flags=re.M)


support_cli = typer.Typer(cls=NaturalOrderGroup)


def _install_debs(debs: list[str]) -> None:
    """
    Install a list of debian packages.

    If they have an http:// or https://
    prefix then they will be downloaded and installed from file.

    args: debs: List[str] - list of debian packages to install - can also include
                            any additional 'apt-get install' options required
    """
    temp = Path("/tmp")
    for i, pkg in enumerate(debs):
        if pkg.startswith("http://") or pkg.startswith("https://"):
            pkg_file = temp / pkg.split("/")[-1]
            subprocess.call(["busybox", "wget", pkg, "-O", str(pkg_file)])
            debs[i] = str(pkg_file)

    if len(debs) == 0:
        print("no packages to install")
        return

    print("installing packages: ", debs)

    sudo = "sudo" if os.geteuid() != 0 else ""
    command = (
        f"{sudo} apt-get update && {sudo} apt-get upgrade -y && "
        f"{sudo} apt-get install -y --no-install-recommends "
        + " ".join(debs)
        + f" && {sudo} rm -rf /var/lib/apt/lists/*"
    )
    exit(subprocess.call(["bash", "-c", command]))


# TODO this should be deprecated in favor of an additional Ansible role
@support_cli.command()
def apt_install_runtime_packages():
    """
    Install packages from the list collected by calls to add_runtime_packages
    """
    if GLOBALS.RUNTIME_DEBS.exists():
        debs = GLOBALS.RUNTIME_DEBS.read_text().split()
        _install_debs(debs)


@support_cli.command()
def generate_schema(
    output: Annotated[
        Path | None,
        typer.Option(
            help="The filename to write the schema to",
            autocompletion=lambda: [],  # Forces path autocompletion
        ),
    ] = None,
):
    """Produce JSON global schema for all <support_module>.ibek.support.yaml files"""
    if output is None:
        typer.echo(Support.get_schema())
    else:
        output.write_text(Support.get_schema())
