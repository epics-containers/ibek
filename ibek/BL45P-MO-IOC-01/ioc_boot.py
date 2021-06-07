import json
from pathlib import Path
from typing import List, Optional

import typer
from apischema.json_schema import deserialization_schema
from jinja2 import Template
from ruamel.yaml import YAML

from ibek import __version__
from ibek.pmac import EntityInstance, PmacIOC

yaml = YAML()
app = typer.Typer()


@app.command()
def create_schema(save_path: str) -> None:
    with open(save_path, "w") as f:
        json.dump(deserialization_schema(PmacIOC), f)


def render_script_elements(ioc_instance) -> str:
    scripts = ""
    for instance in ioc_instance.instances:
        for script in instance.create_scripts():
            scripts += (Template(script).render(instance.__dict__)) + "\n"
    return scripts


def create_database_elements(ioc_instance) -> str:
    databases = ""
    for instance in ioc_instance.instances:
        for database in instance.create_database():
            databases += Template(database).render(instance.__dict__) + "\n"
    return databases


@app.command()
def create_boot_script(ioc_instance_yaml_path):
    with open(ioc_instance_yaml_path, "r") as f:
        ioc_instance = PmacIOC.deserialize(yaml.load(f))

    with open(Path(__file__).parent / "startup_script.txt", "r") as f:
        template = Template(f.read())

    template = template.render(
        script_elements=render_script_elements(ioc_instance),
        database_elements=create_database_elements(ioc_instance),
    )
    print(template)
    return template


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


# def main(
#     ioc_instance_yaml_path: str = (Path(__file__).parent / "bl45p-mo-ioc-02.pmac.yaml"),
# ):

#     boot_script = create_boot_script(ioc_instance_yaml_path)
#     print(boot_script)


# if __name__ == "__main__":
#     main()

if __name__ == "__main__":
    app()
