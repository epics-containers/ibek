"""
Functions for building the helm chart
"""

import shutil
from pathlib import Path
from typing import Tuple

from jinja2 import Template
from ruamel.yaml.main import YAML

from .ioc import IOC, make_entity_classes
from .render import render_database_elements, render_script_elements
from .support import Support

HELM_TEMPLATE = Path(__file__).parent.parent / "helm-template"
TEMPLATES = Path(__file__).parent / "templates"


def create_boot_script(
    ioc_instance_yaml: Path, definition_yaml: Path
) -> Tuple[IOC, str]:
    """
    Create the boot script for an IOCs helm chart
    """
    # Read and load the support module definitions
    support = Support.deserialize(YAML().load(definition_yaml))
    make_entity_classes(support)

    # Create an IOC instance from it
    ioc_instance = IOC.deserialize(YAML().load(ioc_instance_yaml))

    # Open jinja template for startup script and fill it in with script
    # elements and database elements parsed from the defintion file
    with open(TEMPLATES / "ioc.boot.jinja", "r") as f:
        template = Template(f.read())

    script_txt = template.render(
        script_elements=render_script_elements(ioc_instance),
        database_elements=render_database_elements(ioc_instance),
    )

    return ioc_instance, script_txt


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


def create_helm(instance: IOC, script_txt: str, path: Path):
    """
    create a boilerplate helm chart with name str in folder path

    update the values.yml and Chart.yml by rendering their jinja templates
    and insert the boot script whose text is supplied in script_txt
    """
    helm_folder = path / instance.ioc_name

    if path.exists():
        if helm_folder.exists():
            shutil.rmtree(helm_folder)
    else:
        # fail if parent does not exist (usually the iocs folder)
        path.mkdir()

    shutil.copytree(HELM_TEMPLATE, helm_folder)

    render_file(
        helm_folder / "Chart.yaml.jinja",
        ioc_name=instance.ioc_name,
        description=instance.description,
    )
    render_file(
        helm_folder / "values.yaml.jinja",
        base_image="gcr.io/diamond-pubreg/controls/prod/ioc/ioc-pmac:2.5.3",
    )

    boot_script_path = helm_folder / "config" / "ioc.boot"

    # Saves rendered boot script
    with open(boot_script_path, "w") as f:
        f.write(script_txt)
