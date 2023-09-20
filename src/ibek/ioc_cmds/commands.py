import json
from pathlib import Path
from typing import List

import typer
from jinja2 import Template

from ibek.gen_scripts import ioc_create_model
from ibek.globals import IOC_DBDS, IOC_LIBS, MAKE_FOLDER, MODULES, SCRIPTS_FOLDER

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


@ioc_cli.command()
def generate_makefile():
    """
    get the dbd and lib files from all support modules and generate
    iocApp/src/Makefile from iocApp/src/Makefile.jinja
    """

    # use modules file to get a list of all support module folders
    # in the order of build (and hence dependency)
    modules: List[str] = MODULES.read_text().split()[2:]
    # remove the IOC folder from the list
    if "IOC" in modules:
        modules.remove("IOC")

    # get all the dbd and lib files gathered from each support module
    dbds = [dbd.strip() for dbd in IOC_DBDS.read_text().split()]
    libs = [lib.strip() for lib in IOC_LIBS.read_text().split()]

    # generate the Makefile from the template
    template = Template((MAKE_FOLDER / "Makefile.jinja").read_text())
    # libraries are listed in reverse order of dependency
    libs.reverse()
    text = template.render(dbds=dbds, libs=libs)

    with (MAKE_FOLDER / "Makefile").open("w") as stream:
        stream.write(text)


@ioc_cli.command()
def compile():
    """Compile a generic IOC once all support modules are registered and compiled"""
