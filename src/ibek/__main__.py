import json
from pathlib import Path
from typing import List, Optional

import typer
from ruamel.yaml import YAML

from ._version import __version__
from .gen_scripts import create_boot_script, create_db_script, ioc_deserialize
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
    """Produce JSON global schema for all <support_module>.ibek.support.yaml files"""
    output.write_text(Support.get_schema())


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

    for definition in definitions:
        support_dict = YAML(typ="safe").load(definition)
        if not no_schema:
            # Verify the schema of the support module definition file
            Support.model_validate(support_dict)

        # deserialize the support module definition file
        support = Support(**support_dict)
        # make Entity classes described in the support module definition file
        make_entity_classes(support)

    # Save the schema for IOC - it will include all subclasses of Entity
    # that were created in the global namespace by make_entity_classes
    schema = json.dumps(IOC.model_json_schema(), indent=2)
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
