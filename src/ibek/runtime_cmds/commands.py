from pathlib import Path
from typing import List

import typer

from ibek.gen_scripts import (
    create_boot_script,
    create_db_script,
    ioc_deserialize,
)
from ibek.globals import NaturalOrderGroup

runtime_cli = typer.Typer(cls=NaturalOrderGroup)


@runtime_cli.command()
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

    ## TODO TODO
    # here we want add generation of bob files from PVI files
    # and also make a bob index file of buttons
    #
    # you can access the 'opi' definition like this:
    # ioc_instance.entities[0].__definition__.opis()

    ioc_instance = ioc_deserialize(instance, definitions)

    script_txt = create_boot_script(ioc_instance)

    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w") as stream:
        stream.write(script_txt)

    db_txt = create_db_script(ioc_instance)

    with db_out.open("w") as stream:
        stream.write(db_txt)
