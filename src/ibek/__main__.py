import json
from pathlib import Path
from typing import Any, List, Mapping, Optional

import jsonschema
import typer
from apischema.json_schema import JsonSchemaVersion, deserialization_schema
from ruamel.yaml import YAML

from ibek import __version__

from .gen_scripts import create_boot_script, create_db_script, ioc_deserialize
from .ioc import IOC, make_entity_classes
from .support import Support

cli = typer.Typer()
yaml = YAML()


def make_schema(cls: type) -> Mapping[str, Any]:
    return deserialization_schema(cls, version=JsonSchemaVersion.DRAFT_7)


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
    """Produce JSON global schema for all <support_module>.ibek.support.yaml files"""
    schema = json.dumps(make_schema(Support), indent=2)
    output.write_text(schema)


@cli.command()
def ioc_schema(
    definitions: List[Path] = typer.Argument(
        ..., help="The filepath to a support module definition file"
    ),
    output: Path = typer.Argument(..., help="The filename to write the schema to"),
    no_schema: bool = typer.Option(False, help="disable schema checking"),
):
    """
    Create a json schema from a <support_module>.ibek.support.yaml file
    """

    # first check the definition file with jsonschema since it has more
    # legible error messages than apischema
    for definition in definitions:
        support_dict = YAML(typ="safe").load(definition)
        if not no_schema:
            schema_support = make_schema(Support)
            jsonschema.validate(support_dict, schema_support)

        support = Support.deserialize(support_dict)
        make_entity_classes(support)

    schema = json.dumps(make_schema(IOC), indent=2)
    output.write_text(schema)


@cli.command()
def build_startup(
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
        default="config/make_db.sh",
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
