import json
from pathlib import Path
from typing import Optional

import jsonschema
import typer
from apischema.json_schema import deserialization_schema
from ruamel.yaml import YAML

from ibek import __version__

from .helm import create_boot_script, create_helm, load_ioc_yaml
from .ioc import IOC, make_entity_classes
from .support import Support

cli = typer.Typer()
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
    """Do 3 things..."""


@cli.command()
def ibek_schema(
    output: Path = typer.Argument(..., help="The filename to write the schema to")
):
    """Produce the JSON global schema for all <support_module>.ibek.yaml files"""
    schema = json.dumps(deserialization_schema(Support), indent=2)
    output.write_text(schema)


@cli.command()
def ioc_schema(
    definition: Path = typer.Argument(
        ..., help="The filepath to a support module definition file"
    ),
    output: Path = typer.Argument(..., help="The filename to write the schema to"),
):
    """
    Create a json schema from a <support_module>.ibek.yaml file
    TODO: update to take multiple definition files from a container
    """

    # first check the definition file with jsonschema since it has more
    # legible error messages than apischema
    support_dict = YAML().load(definition)
    schema_support = deserialization_schema(Support)
    jsonschema.validate(support_dict, schema_support)

    support = Support.deserialize(support_dict)
    make_entity_classes(support)
    schema = json.dumps(deserialization_schema(IOC), indent=2)
    output.write_text(schema)


@cli.command()
def build_helm(
    entity: Path = typer.Argument(
        ..., help="The filepath to the ioc instance entity file"
    ),
    out: Path = typer.Argument(
        default="iocs", help="Path in which to build the helm chart"
    ),
    no_schema: bool = typer.Option(False, help="disable schema checking"),
):
    """
    Build a startup script, database and Helm chart from <ioc>.yaml
    """

    ioc_dict = load_ioc_yaml(ioc_instance_yaml=entity, no_schema=no_schema)

    with entity.open("r") as stream:
        entity_yaml = stream.read()

    create_helm(ioc_dict=ioc_dict, entity_yaml=entity_yaml, path=out)


@cli.command()
def build_startup(
    instance: Path = typer.Argument(
        ..., help="The filepath to the ioc instance entity file"
    ),
    definition: Path = typer.Argument(
        ..., help="The filepath to a support module definition file"
    ),
    out: Path = typer.Argument(
        default="config/ioc.boot", help="Path to output startup script"
    ),
):
    """
    Build a startup script for an IOC instance
    TODO: update to take multiple definition files from a container
    """
    script_txt = create_boot_script(
        ioc_instance_yaml=instance, definition_yaml=definition
    )

    with out.open("w") as stream:
        stream.write(script_txt)


# test with:
#     pipenv run python -m ibek
if __name__ == "__main__":
    cli()
