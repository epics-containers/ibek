import json
from pathlib import Path
from typing import List

import typer

from ibek.gen_scripts import ioc_create_model

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
