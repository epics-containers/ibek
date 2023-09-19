import json
from pathlib import Path
from typing import List, Optional

import typer
from ruamel.yaml import YAML

from ibek.generic_ioc.commands import support_cli

from ._version import __version__
from .gen_scripts import (
    create_boot_script,
    create_db_script,
    ioc_create_model,
    ioc_deserialize,
)

cli = typer.Typer()
startup_cli = typer.Typer()
ioc_cli = typer.Typer()


cli.add_typer(
    support_cli,
    name="support",
    help="Commands for building support modules during container build",
)
cli.add_typer(
    ioc_cli,
    name="ioc",
    help="Commands for building generic IOCs during container build",
)
cli.add_typer(
    startup_cli,
    name="startup",
    help="Commands for building IOC instance startup files at container runtime",
)

yaml = YAML()


def version_callback(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@cli.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Print the version of ibek and exit",
    )
):
    """IOC Builder for EPICS and Kubernetes

    Provides support for building generic EPICS IOC container images and for
    running IOC instances in a Kubernetes cluster.
    """


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


@startup_cli.command()
def generate(
    instance: Path = typer.Argument(
        ..., help="The filepath to the ioc instance entity file"
    ),
    definitions: List[Path] = typer.Argument(
        ..., help="The filepath to a support module definition file"
    ),
    out: Path = typer.Option(
        default="config/st.cmd",
        help="Path to output startup script",
    ),
    db_out: Path = typer.Option(
        default="config/db.subst",
        help="Path to output database expansion shell script",
    ),
):
    """
    Build a startup script for an IOC instance
    """

    ioc_instance = ioc_deserialize(instance, definitions)

    script_txt = create_boot_script(ioc_instance)

    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w") as stream:
        stream.write(script_txt)

    db_txt = create_db_script(ioc_instance)

    with db_out.open("w") as stream:
        stream.write(db_txt)


# test with:
#     pipenv run python -m ibek
if __name__ == "__main__":
    cli()
