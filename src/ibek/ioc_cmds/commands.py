import json
import logging
from pathlib import Path
from typing import Annotated, List, Optional

import typer

from ibek.entity_factory import EntityFactory
from ibek.globals import (
    GLOBALS,
    SUPPORT_YAML_PATTERN,
    NaturalOrderGroup,
)
from ibek.ioc_cmds.docker import build_dockerfile
from ibek.ioc_factory import IocFactory

from .assets import extract_assets

log = logging.getLogger(__name__)
ioc_cli = typer.Typer(cls=NaturalOrderGroup)


@ioc_cli.command()
def build_docker(
    start: int = typer.Option(1, help="The step to start at in the Dockerfile"),
    stop: int = typer.Option(999, help="The step to stop at in the Dockerfile"),
    dockerfile: Annotated[
        Path,
        typer.Option(
            help="The filepath to the Dockerfile to build",
            autocompletion=lambda: [],  # Forces path autocompletion
        ),
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
        None,  # Note: typer converts None to an empty list because the type is List
        help="File paths to one or more support module YAML files",
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
    output: Annotated[
        Optional[Path],
        typer.Option(
            help="The file path to the schema file to be written",
            autocompletion=lambda: [],  # Forces path autocompletion
        ),
    ] = None,
    ibek_defs: bool = typer.Option(
        True, help=f"Include definitions in {GLOBALS.IBEK_DEFS} in generated schema"
    ),
):
    """
    Create a json schema from a number of support_module.ibek.support.yaml
    files
    """
    if not (definitions or ibek_defs):
        log.error("One or more `definitions` required with `--no-ibek-defs`")
        raise typer.Exit(1)

    definitions = definitions or []

    if ibek_defs:
        # this allows us to use the definitions inside the container
        # which are in a known location after the container is built
        definitions += GLOBALS.IBEK_DEFS.glob(SUPPORT_YAML_PATTERN)

    if not definitions:
        log.error(f"No `definitions` given and none found in {GLOBALS.IBEK_DEFS}")
        raise typer.Exit(1)

    entity_factory = EntityFactory()
    entity_models = entity_factory.make_entity_models(definitions)
    ioc_factory = IocFactory()
    ioc_model = ioc_factory.make_ioc_model(entity_models)

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
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
    extras: List[Path] = typer.Argument(None, help="list of files to also extract"),
    source: Path = typer.Option(
        Path("/epics"),
        help="The root folder to extract assets from",
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
    defaults: bool = typer.Option(True, help="copy the default assets"),
    dry_run: bool = typer.Option(False, help="show what would happen"),
):
    """
    Find all the runtime assets in an EPICS installation and copy them to a
    new folder hierarchy for packaging into a container runtime stage.

    This should be performed in a throw away container stage (runtime_prep)
    as it is destructive of the source folder, because it uses move for speed.
    """
    extras = extras or []
    extract_assets(destination, source, extras, defaults, dry_run)
