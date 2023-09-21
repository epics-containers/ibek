import json
import subprocess
from pathlib import Path
from typing import Annotated, List

import typer
from jinja2 import Template

from ibek.gen_scripts import ioc_create_model
from ibek.globals import (
    IOC_DBDS,
    IOC_FOLDER,
    IOC_LIBS,
    MAKE_FOLDER,
    MODULES,
    PROJECT_ROOT_FOLDER,
)
from ibek.ioc_cmds.docker import build_dockerfile

ioc_cli = typer.Typer()


@ioc_cli.command()
def generate_schema(
    definitions: List[Path] = typer.Argument(
        ..., help="The filepath to a support module definition file"
    ),
    output: Path = typer.Argument(..., help="The filename to write the schema to"),
):
    """
    Create a json schema from a <support_module>.ibek.support.yaml file
    """

    ioc_model = ioc_create_model(definitions)
    schema = json.dumps(ioc_model.model_json_schema(), indent=2)
    output.write_text(schema)


@ioc_cli.command()
def generate_makefile():
    """
    get the dbd and lib files from all support modules and generate
    iocApp/src/Makefile from iocApp/src/Makefile.jinja
    """

    # use modules file to get a list of all support module folders
    # in the order of build (and hence dependency)
    modules: List[str] = MODULES.read_text().split()[2:]
    # remove the IOC folder from the list
    if "IOC" in modules:
        modules.remove("IOC")

    # get all the dbd and lib files gathered from each support module
    dbds = [dbd.strip() for dbd in IOC_DBDS.read_text().split()]
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
    ] = PROJECT_ROOT_FOLDER
    / "Dockerfile",
):
    """
    Attempt to interpret the Dockerfile and run the commands inside the
    developer container.

    Useful for debugging the Dockerfile without having to build the whole
    container from outside of the IOC devcontainer.

    EXPERIMENTAL FEATURE
    """
    build_dockerfile(dockerfile, start, stop)
