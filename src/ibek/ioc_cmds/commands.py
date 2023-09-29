import json
import shutil
import subprocess
from pathlib import Path
from typing import Annotated, List, Optional

import typer
from jinja2 import Template

from ibek.gen_scripts import ioc_create_model
from ibek.globals import (
    IOC_DBDS,
    IOC_FOLDER,
    IOC_LIBS,
    MAKE_FOLDER,
    TEMPLATES,
    NaturalOrderGroup,
)
from ibek.ioc_cmds.docker import build_dockerfile

from .assets import extract_assets

ioc_cli = typer.Typer(cls=NaturalOrderGroup)


@ioc_cli.command()
def generate_makefile() -> None:
    """
    get the dbd and lib files from all support modules and generate
    iocApp/src/Makefile from iocApp/src/Makefile.jinja
    """
    # get all the dbd and lib files gathered from each support module
    dbds: List[str] = []
    libs: List[str] = []
    if IOC_DBDS.exists():
        dbds = [dbd.strip() for dbd in IOC_DBDS.read_text().split()]
    if IOC_LIBS.exists():
        libs = [lib.strip() for lib in IOC_LIBS.read_text().split()]

    # generate the Makefile from the template
    template = Template((MAKE_FOLDER / "Makefile.jinja").read_text())
    # libraries are listed in reverse order of dependency
    libs.reverse()
    text = template.render(dbds=dbds, libs=libs)

    with (MAKE_FOLDER / "Makefile").open("w") as stream:
        stream.write(text)


@ioc_cli.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def compile(
    ctx: typer.Context,
):
    """
    Compile a generic IOC after support modules are registered and compiled
    """
    path = IOC_FOLDER

    command = f"make -C {path} -j $(nproc) " + " ".join(ctx.args)
    exit(subprocess.call(["bash", "-c", command]))


@ioc_cli.command()
def build(
    start: int = typer.Option(1, help="The step to start at in the Dockerfile"),
    stop: int = typer.Option(999, help="The step to stop at in the Dockerfile"),
    dockerfile: Annotated[
        Path, typer.Option(help="The filepath to the Dockerfile to build")
    ] = Path.cwd()
    / "Dockerfile",
):
    """
    EXPERIMENTAL: Attempt to interpret the Dockerfile and run it's commands
    inside the devcontainer. For internal, incremental builds of the Dockerfile.

    Useful for debugging the Dockerfile without having to build the whole
    container from outside of the IOC devcontainer.
    """
    build_dockerfile(dockerfile, start, stop)


@ioc_cli.command()
def generate_schema(
    definitions: List[Path] = typer.Argument(
        ...,
        help="File paths to one or more support module YAML files",
    ),
    output: Annotated[
        Optional[Path],
        typer.Option(help="The file path to the schema file to be written"),
    ] = None,
):
    """
    Create a json schema from a number of support_module.ibek.support.yaml
    files
    """

    ioc_model = ioc_create_model(definitions)
    schema = json.dumps(ioc_model.model_json_schema(), indent=2)
    if output is None:
        print(schema)
    else:
        output.write_text(schema)


@ioc_cli.command()
def extract_runtime_assets(
    destination: Path = typer.Argument(
        ...,
        help="The root folder to extract assets into",
    ),
    source: Path = typer.Option(
        Path("/epics"),
        help="The root folder to extract assets from",
    ),
    extras: List[Path] = typer.Option(None, help="list of files to also extract"),
    defaults: bool = typer.Option(True, help="copy the default assets"),
):
    extract_assets(destination, source, extras, defaults)


@ioc_cli.command()
def make_source_template(
    destination: Path = typer.Argument(
        Path.cwd().parent / "ioc",
        help="The root folder in which to place the IOC boilerplate",
    )
):
    """
    Create a new IOC boilerplate source tree in the given folder.
    Default is ../ioc. Typically call this when CWD is
    <generic_ioc_root>/ibek-support as this is the standard
    Dockerfile WORKDIR.
    """
    if destination.exists():
        typer.echo(f"{destination} IOC source exists, skipping ...")
    else:
        shutil.copytree(TEMPLATES / "ioc", destination)
        typer.echo(f"Created IOC source tree in {destination}")

    try:
        IOC_FOLDER.unlink(missing_ok=True)
    except IsADirectoryError:
        shutil.rmtree(IOC_FOLDER)
    IOC_FOLDER.symlink_to(destination)
