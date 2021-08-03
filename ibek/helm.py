"""
functions for building the helm chart
"""

import shutil
from pathlib import Path

from jinja2 import Template
from ruamel.yaml.main import YAML

from ibek.dataclass_from_yaml import yaml_to_dataclass
from ibek.render import render_database_elements, render_script_elements

HELM_TEMPLATE = Path(__file__).parent.parent / "helm-template"
TEMPLATES = Path(__file__).parent / "templates"


def create_boot_script(ioc_yaml: Path, save_file: Path, ioc_class_ibek_yaml: Path):
    # Dynamically generate a Support object graph for this class of ioc
    support = yaml_to_dataclass(str(ioc_class_ibek_yaml))

    # populate its dataclass namespace
    support_entities = support.get_module_dataclass()

    # Opens jinja template for startup script and fills it in with script
    # elements and database elements parsed from the <ioc_name>.yaml file

    with open(TEMPLATES / "ioc.boot.jinja", "r") as f:
        template = Template(f.read())

    # read the ioc instance definition into a dictionary
    entity_instance_dict = YAML().load(ioc_yaml)
    # use the
    entity_instances = support_entities.deserialize(entity_instance_dict)

    boot_script = template.render(
        script_elements=render_script_elements(entity_instances),
        database_elements=render_database_elements(entity_instances),
    )
    # Saves rendered boot script
    with open(save_file, "w") as f:
        f.write(boot_script)


def render_file(file_template: Path, **kwargs):
    """
    replace a jinja templated file with its rendered equivalent by using
    kwargs parameters to jinja
    """
    template = file_template.read_text()
    text = Template(template).render(kwargs)

    file = Path(str(file_template).replace(".jinja", ""))
    file.write_text(text)
    file_template.unlink()


def create_helm(name: str, path: Path):
    """
    create a boilerplate helm chart with name str in folder path
    """
    helm_folder = path / name

    if path.exists():
        if helm_folder.exists():
            shutil.rmtree(helm_folder)
    else:
        path.mkdir(parents=True)

    shutil.copytree(HELM_TEMPLATE, helm_folder)

    # TODO description should come from the ioc yaml
    render_file(helm_folder / "Chart.yaml.jinja", ioc_name=name, description="an ioc")
    render_file(
        helm_folder / "values.yaml.jinja",
        base_image="gcr.io/diamond-pubreg/controls/prod/ioc/ioc-pmac:2.5.3",
    )

    boot_script_path = helm_folder / "config" / "ioc.boot"
    return boot_script_path
