import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Annotated, List, Optional

import typer
from jinja2 import Template

from ibek.gen_scripts import ioc_create_model
from ibek.globals import (
    IBEK_DEFS,
    IOC_DBDS,
    IOC_FOLDER,
    IOC_LIBS,
    SUPPORT_YAML_PATTERN,
    TEMPLATES,
    NaturalOrderGroup,
)
from ibek.ioc_cmds.docker import build_dockerfile

from .assets import extract_assets, get_ioc_source

log = logging.getLogger(__name__)
ioc_cli = typer.Typer(cls=NaturalOrderGroup)


@ioc_cli.command()
def build_docker(
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
        None,
        help="File paths to one or more support module YAML files",
    ),
    output: Annotated[
        Optional[Path],
        typer.Option(help="The file path to the schema file to be written"),
    ] = None,
    use_defs: bool = typer.Option(False, help="Use definitions inside the container"),
):
    """
    Create a json schema from a number of support_module.ibek.support.yaml
    files
    """
    if use_defs:
        # this allows us to use the definitions inside the container
        # which are in a known location after the container is built
        definitions += IBEK_DEFS.glob(SUPPORT_YAML_PATTERN)
    else:
        if len(definitions) == 0:
            log.error("Provide support YAML definitions or --use-defs")
            raise typer.Exit(1)

    ioc_model = ioc_create_model(definitions)
    schema = json.dumps(ioc_model.model_json_schema(), indent=2)
    if output is None:
        typer.echo(schema)
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
    """
    Find all the runtime assets in an EPICS installation and copy them to a
    new folder hierarchy for packaging into a container runtime stage.

    This should be performed in a throw away container stage (runtime_prep)
    as it is destructive of the source folder, because it uses move for speed.
    """
    extract_assets(destination, source, extras, defaults)


@ioc_cli.command()
def make_source_template(
    destination: Annotated[
        Optional[Path],
        typer.Option(
            help="Where to make the ioc folder. Defaults to under the "
            "generic IOC source folder",
        ),
    ] = None,
):
    """
    Create a new IOC boilerplate source tree in the given folder.
    Default is ioc source repo / ioc .
    """
    if destination is None:
        destination = get_ioc_source() / "ioc"

    if not destination.exists():
        if destination.is_symlink():
            destination.unlink()
        shutil.copytree(TEMPLATES / "ioc", destination)

    # make a symlink to the ioc folder in the root of the epics folder
    # this becomes the standard place for code to look for the IOC
    try:
        IOC_FOLDER.unlink(missing_ok=True)
    except IsADirectoryError:
        shutil.rmtree(IOC_FOLDER)
    IOC_FOLDER.symlink_to(destination)


@ioc_cli.command()
def generate_makefile(
    folder_override: Annotated[
        Optional[Path],
        typer.Option(
            help="Where to find the Makefile.jinja template.",
        ),
    ] = None,
):
    """
    get the dbd and lib files from all support modules and generate
    iocApp/src/Makefile from iocApp/src/Makefile.jinja
    """
    # Folder containing Makefile.jinja
    make_folder = folder_override or get_ioc_source() / "ioc" / "iocApp" / "src"

    # get all the dbd and lib files gathered from each support module
    dbds: List[str] = []
    libs: List[str] = []
    if IOC_DBDS.exists():
        dbds = [dbd.strip() for dbd in IOC_DBDS.read_text().split()]
    if IOC_LIBS.exists():
        libs = [lib.strip() for lib in IOC_LIBS.read_text().split()]

    # generate the Makefile from the template
    template = Template((make_folder / "Makefile.jinja").read_text())
    # libraries are listed in reverse order of dependency
    libs.reverse()
    text = template.render(dbds=dbds, libs=libs)

    with (make_folder / "Makefile").open("w") as stream:
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


@ioc_cli.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def build(
    ctx: typer.Context,
):
    """
    A convenience function that calls make-source-template, generate-makefile,
    compile
    """
    make_source_template()
    generate_makefile()
    compile(ctx)
