import json
import shutil
from pathlib import Path
from typing import Optional

import typer
from apischema.json_schema import deserialization_schema
from jinja2 import Template
from ruamel.yaml import YAML

from ibek import __version__
from ibek.pmac import PmacIOC

THIS_FOLDER = Path(__file__).parent

yaml = YAML()
app = typer.Typer()

# Have a dummy function return PmacIOC to simulate building class from yaml


def generate_instance_datamodel(ioc_class_ibek_yaml: Path):
    # This function currently returns PmacIOC for demonstration purposes and will do so for any path given
    # This should be replaced by a function that uses the Support module to dynamically create a datamodel
    # in memory from the <ioc_class>.ibek.yaml file
    return PmacIOC


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
def ioc_schema(save_path: Path, ioc_class_ibek_yaml: Path) -> None:
    """ Produce the JSON schema from inside an IOC container """
    with open(save_path, "w") as f:
        json.dump(
            deserialization_schema(generate_instance_datamodel(ioc_class_ibek_yaml)),
            f,
            indent=2,
        )


def create_boot_script(ioc_yaml: Path, save_file: Path, ioc_class_ibek_yaml: Path):
    with ioc_yaml.open("r") as f:

        # Dynamically generate a class for this class of ioc from its <ioc_class>.ibek.yaml
        ioc_instance = generate_instance_datamodel(ioc_class_ibek_yaml).deserialize(
            yaml.load(f)
        )

    with open(THIS_FOLDER / "startup_script.txt", "r") as f:
        template = Template(f.read())

    boot_script = template.render(
        script_elements=render_script_elements(ioc_instance),
        database_elements=create_database_elements(ioc_instance),
    )
    print(boot_script)
    with open(save_file, "w") as f:
        f.write(boot_script)


def render_file(file_template: Path, **kwargs):
    template = file_template.read_text()
    text = Template(template).render(kwargs)
    file = Path(str(file_template).replace(".jinja", ""))
    file.write_text(text)
    file_template.unlink()


def create_helm(ioc_yaml: Path):
    ioc_name = str(ioc_yaml.stem).split(".")[0]
    helm_folder = Path("ioc") / ioc_name
    print(f"helm will be {helm_folder}")

    shutil.rmtree(helm_folder)
    shutil.copytree(THIS_FOLDER.parent.parent / "helm-template", helm_folder)
    # TODO description should come from the ioc yaml
    render_file(
        helm_folder / "Chart.yaml.jinja", ioc_name=ioc_name, description="an ioc"
    )
    render_file(
        helm_folder / "values.yaml.jinja",
        base_image="gcr.io/diamond-pubreg/controls/prod/ioc/ioc-pmac:2.5.3",
    )

    boot_script_file = helm_folder / "config" / "ioc.boot"
    return boot_script_file


@app.command()
def build_ioc(
    ioc_yaml: Path = typer.Argument(
        ..., help="The yaml file describing this IOC instance"
    ),
):
    """Build a startup script and Helm chart from <ioc>.yaml """
    boot_script = create_helm(ioc_yaml=ioc_yaml)
    create_boot_script(ioc_yaml=ioc_yaml, save_file=boot_script)


if __name__ == "__main__":
    app()
