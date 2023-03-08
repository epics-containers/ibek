"""
Functions for building the db and boot scripts
"""
import logging
import re
from pathlib import Path
from typing import List

from jinja2 import Template
from ruamel.yaml.main import YAML

from .ioc import IOC, make_entity_classes
from .render import (
    render_database_elements,
    render_environment_variable_elements,
    render_post_ioc_init_elements,
    render_pre_ioc_init_elements,
    render_script_elements,
)
from .support import Support

log = logging.getLogger(__name__)

TEMPLATES = Path(__file__).parent / "templates"

schema_modeline = re.compile(r"# *yaml-language-server *: *\$schema=([^ ]*)")
url_f = r"file://"


def ioc_deserialize(ioc_instance_yaml: Path, definition_yaml: List[Path]) -> IOC:
    """
    Takes an ioc instance entities file, list of generic ioc definitions files.

    Returns an in memory object graph of the resulting ioc instance
    """
    # Read and load the support module definitions
    for yaml in definition_yaml:
        support = Support.deserialize(YAML(typ="safe").load(yaml))
        make_entity_classes(support)

    # Create an IOC instance from it
    return IOC.deserialize(YAML(typ="safe").load(ioc_instance_yaml))


def create_db_script(ioc_instance: IOC) -> str:
    """
    Create make_db.sh script for expanding the database templates
    """
    with open(TEMPLATES / "make_db.jinja", "r") as f:
        template = Template(f.read())

    return template.render(database_elements=render_database_elements(ioc_instance))


def create_boot_script(ioc_instance: IOC) -> str:
    """
    Create the boot script for an IOC
    """
    with open(TEMPLATES / "st.cmd.jinja", "r") as f:
        template = Template(f.read())

    return template.render(
        env_var_elements=render_environment_variable_elements(ioc_instance),
        script_elements=render_script_elements(ioc_instance),
        post_ioc_init_elements=render_post_ioc_init_elements(ioc_instance),
        pre_ioc_init_elements=render_pre_ioc_init_elements(ioc_instance),
    )
