"""
functions for building the helm chart
"""

import shutil
from pathlib import Path
from typing import Tuple

from jinja2 import Template
from ruamel.yaml.main import YAML

from ibek.render import render_database_elements, render_script_elements
from ibek.support import IocInstance

HELM_TEMPLATE = Path(__file__).parent.parent / "helm-template"
TEMPLATES = Path(__file__).parent / "templates"


def create_boot_script(
    ioc_instance_yaml: Path, definition_yaml: Path
) -> Tuple[str, str]:
    """
    Create the boot script for an IOCs helm chart
    """

    # Dynamically generate dataclasses from the support module defintion file
    support_definition = IocInstance.from_yaml(definition_yaml)

    # Open jinja template for startup script and fill it in with script
    # elements and database elements parsed from the defintion file
    with open(TEMPLATES / "ioc.boot.jinja", "r") as f:
        template = Template(f.read())

    # read the ioc instance entities into a dictionary
    entity_instance_dict = YAML().load(ioc_instance_yaml)

    # Use the support defintion classes to deserialize the ioc instance entities
    entity_instances = support_definition.deserialize(entity_instance_dict)

    script_txt = template.render(
        script_elements=render_script_elements(entity_instances),
        database_elements=render_database_elements(entity_instances),
    )

    return entity_instances.ioc_name, script_txt


def render_file(file_template: Path, **kwargs):
    """
    replace a jinja templated file with its rendered equivalent by passing
    kwargs parameters to jinja
    """
    template = file_template.read_text()
    text = Template(template).render(kwargs)

    file = Path(str(file_template).replace(".jinja", ""))
    file.write_text(text)
    file_template.unlink()


def create_helm(name: str, script_txt: str, path: Path):
    """
    create a boilerplate helm chart with name str in folder path

    update the values.yml and Chart.yml by rendering their jinja templates
    and insert the boot script whose text is supplied in script_txt
    """
    helm_folder = path / name

    if path.exists():
        if helm_folder.exists():
            shutil.rmtree(helm_folder)
    else:
        # fail if parent does not exist (usually the iocs folder)
        path.mkdir()

    shutil.copytree(HELM_TEMPLATE, helm_folder)

    # TODO description should come from the ioc yaml
    render_file(helm_folder / "Chart.yaml.jinja", ioc_name=name, description="an ioc")
    render_file(
        helm_folder / "values.yaml.jinja",
        base_image="gcr.io/diamond-pubreg/controls/prod/ioc/ioc-pmac:2.5.3",
    )

    boot_script_path = helm_folder / "config" / "ioc.boot"

    # Saves rendered boot script
    with open(boot_script_path, "w") as f:
        f.write(script_txt)
