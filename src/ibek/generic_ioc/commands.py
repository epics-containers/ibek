from pathlib import Path

import typer

from ibek.support import Support

support_cli = typer.Typer()


@support_cli.command()
def generate_schema(
    output: Path = typer.Argument(..., help="The filename to write the schema to")
):
    """Produce JSON global schema for all <support_module>.ibek.support.yaml files"""
    output.write_text(Support.get_schema())
