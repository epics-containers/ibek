import json
from pathlib import Path
from typing import Optional

import typer
from apischema.json_schema import deserialization_schema
from ruamel.yaml import YAML
from ruamel.yaml.main import YAML

from ibek import __version__
from ibek.generator import from_yaml
from ibek.helm import create_boot_script, create_helm
from ibek.support import Support

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
    """Produce the JSON schema for a <support_module>.ibek.yaml file"""
    schema = json.dumps(deserialization_schema(Support), indent=2)
    with open(output, "w") as f:
        f.write(schema)


@cli.command()
def ioc_schema(
    description: Path = typer.Argument(
        ..., help="The filepath to read the IOC class description from"
    ),
    output: Path = typer.Argument(..., help="The filename to write the schema to"),
):
    """Create a json schema from a <support_module>.ibek.yaml file"""
    ioc_class = from_yaml(description)

    schema = json.dumps(deserialization_schema(ioc_class), indent=2)
    with open(output, "w") as f:
        f.write(schema)


@cli.command()
def build_ioc(
    definition: Path = typer.Argument(
        ..., help="The filepath to the ioc definition file"
    ),
    instance: Path = typer.Argument(..., help="The filepath to the ioc instance file"),
    out: Path = typer.Argument(
        default="iocs", help="Path in which to build the helm chart"
    ),
):
    """Build a startup script, database and Helm chart from <ioc>.yaml"""

    ioc_instance, script_txt = create_boot_script(
        ioc_instance_yaml=instance, definition_yaml=definition
    )

    create_helm(instance=ioc_instance, script_txt=script_txt, path=out)


# test with:
#     pipenv run python -m ibek
if __name__ == "__main__":
    cli()
