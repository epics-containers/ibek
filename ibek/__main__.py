import json
from pathlib import Path
from typing import Optional

import typer
from apischema.json_schema import deserialization_schema

from ibek import __version__
from ibek.support import Support

app = typer.Typer()


def version_callback(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
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


@app.command()
def ibek_schema(
    output: Path = typer.Argument(..., help="The filename to write the schema to")
):
    """Produce the JSON schema for a <support_module>.ibek.yaml file"""
    schema = json.dumps(deserialization_schema(Support), indent=2)
    with open(output, "w") as f:
        f.write(schema)


@app.command()
def ioc_schema():
    """Produce the JSON schema from inside an IOC container"""
    # This involves programmatically making dataclasses using apischema.
    # Ask Tom about this.


@app.command()
def build_ioc():
    """Build a startup script, database and Helm chart from <ioc>.yaml"""
    # Deserialize all the ibek yaml files into Support instances
    # Read the ioc yaml file into dictionaries
    # Read the type of each instance, and get the correct Entity
    # Call format_script on the entity with the rest of the args from the dict
    # Write out the script


# test with:
#     pipenv run python -m ibek
if __name__ == "__main__":
    app()
