"""
Functions for building the db and boot scripts
"""
import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

from jinja2 import Template
from ruamel.yaml.main import YAML

from .ioc import IOC, make_entity_classes
from .render import Render
from .support import Definition, Support
from .utils import Utils

log = logging.getLogger(__name__)

TEMPLATES = Path(__file__).parent / "templates"

schema_modeline = re.compile(r"# *yaml-language-server *: *\$schema=([^ ]*)")
url_f = r"file://"


def ioc_deserialize(ioc_instance_yaml: Path, definition_yaml: List[Path]) -> IOC:
    """
    Takes an ioc instance entities file, list of generic ioc definitions files.

    Returns an in memory object graph of the resulting ioc instance
    """
    all_values: Dict[str, str] = {}

    # Read and load the support module definitions
    for yaml in definition_yaml:
        support = Support.deserialize(YAML(typ="safe").load(yaml))
        for definition in support.defs:
            for value in definition.values:
                all_values[value.name] = value.value
        make_entity_classes(support)
        for definition in support.defs:
            make_entity_context(definition)

    # Create an IOC instance from it
    ioc_instance = IOC.deserialize(YAML(typ="safe").load(ioc_instance_yaml))
    return ioc_instance


def make_entity_context(definition: Definition):
    """
    Create a context dictionary for the given `Entity` instance
    This is for use in Jinja expansion of instances of this Entity
    """
    context = asdict(definition)

    for value in definition.values:
        context[value.name] = value.value

    setattr(definition, "__context__", context)


def create_db_script(ioc_instance: IOC, utility: Utils) -> str:
    """
    Create make_db.sh script for expanding the database templates
    """
    with open(TEMPLATES / "make_db.jinja", "r") as f:
        template = Template(f.read())

    renderer = Render(utility)

    return template.render(
        __util__=utility,
        database_elements=renderer.render_database_elements(ioc_instance),
    )


def create_boot_script(ioc_instance: IOC, utility: Utils) -> str:
    """
    Create the boot script for an IOC
    """
    with open(TEMPLATES / "st.cmd.jinja", "r") as f:
        template = Template(f.read())

    renderer = Render(utility)

    return template.render(
        __util__=utility,
        env_var_elements=renderer.render_environment_variable_elements(ioc_instance),
        script_elements=renderer.render_script_elements(ioc_instance),
        post_ioc_init_elements=renderer.render_post_ioc_init_elements(ioc_instance),
    )
