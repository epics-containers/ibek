import json
from pathlib import Path
from typing import Optional

import typer
from apischema.json_schema import deserialization_schema
from jinja2 import Template
from ruamel.yaml import YAML

from ibek import __version__
from ibek.pmac import PmacIOC

yaml = YAML()
app = typer.Typer()

# Have a dummy function return PmacIOC to simulate building class from yaml


def render_script_elements(ioc_instance: PmacIOC) -> str:
    scripts = ""
    for instance in ioc_instance.instances:
        for script in instance.create_scripts():
            scripts += (Template(script).render(instance.__dict__)) + "\n"
    return scripts


def create_database_elements(ioc_instance: PmacIOC) -> str:
    databases = ""
    for instance in ioc_instance.instances:
        for database in instance.create_database():
            databases += Template(database).render(instance.__dict__) + "\n"
    return databases


def version_callback(value: bool) -> None:
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
def ioc_schema(save_path: str) -> None:
    """ Produce the JSON schema from inside an IOC container """
    with open(save_path, "w") as f:
        json.dump(deserialization_schema(PmacIOC), f, indent=2)


def create_boot_script(ioc_yaml: Path, save_file: Path):
    with open(ioc_yaml, "r") as f:
        ioc_instance = PmacIOC.deserialize(yaml.load(f))

    with open(Path(__file__).parent / "startup_script.txt", "r") as f:
        template = Template(f.read())

    boot_script = template.render(
        script_elements=render_script_elements(ioc_instance),
        database_elements=create_database_elements(ioc_instance),
    )
    print(boot_script)
    with open(save_file, "w") as f:
        f.write(boot_script)


def create_helm():
    pass


@app.command()
def build_ioc(
    ioc_yaml: Path = typer.Argument(
        ..., help="The yaml file describing this IOC instance"
    ),
    boot_script: Path = typer.Argument(..., help="Full path to save boot script to"),
):
    """Build a startup script and Helm chart from <ioc>.yaml """
    create_boot_script(ioc_yaml=ioc_yaml, save_file=boot_script)
    create_helm()


if __name__ == "__main__":
    app()
