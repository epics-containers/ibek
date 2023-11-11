"""
Functions for building the db and boot scripts
"""
import logging
import re
from pathlib import Path
from typing import List, Tuple, Type

from jinja2 import Template
from ruamel.yaml.main import YAML

from .globals import TEMPLATES
from .ioc import IOC, Entity, clear_entity_model_ids, make_entity_models, make_ioc_model
from .render import Render
from .render_db import RenderDb
from .support import Database, Support

log = logging.getLogger(__name__)


schema_modeline = re.compile(r"# *yaml-language-server *: *\$schema=([^ ]*)")
url_f = r"file://"


def ioc_create_model(definitions: List[Path]) -> Type[IOC]:
    """
    Take a list of definitions YAML and create an IOC model from it
    """
    entity_models = []

    clear_entity_model_ids()
    for definition in definitions:
        support_dict = YAML(typ="safe").load(definition)

        Support.model_validate(support_dict)

        # deserialize the support module definition file
        support = Support(**support_dict)
        # make Entity classes described in the support module definition file
        entity_models += make_entity_models(support)

    # Save the schema for IOC
    model = make_ioc_model(entity_models)

    return model


def ioc_deserialize(ioc_instance_yaml: Path, definition_yaml: List[Path]) -> IOC:
    """
    Takes an ioc instance entities file, list of generic ioc definitions files.

    Returns a model of the resulting ioc instance
    """
    ioc_model = ioc_create_model(definition_yaml)

    # extract the ioc instance yaml into a dict
    ioc_instance_dict = YAML(typ="safe").load(ioc_instance_yaml)

    # Create an IOC instance from the instance dict and the model
    ioc_instance = ioc_model(**ioc_instance_dict)

    return ioc_instance


def create_db_script(
    ioc_instance: IOC, extra_databases: List[Tuple[Database, Entity]]
) -> str:
    """
    Create make_db.sh script for expanding the database templates
    """
    with open(TEMPLATES / "ioc.subst.jinja", "r") as f:
        jinja_txt = f.read()

        renderer = RenderDb(ioc_instance)

        templates = renderer.render_database(extra_databases)

        return Template(jinja_txt).render(templates=templates)


def create_boot_script(ioc_instance: IOC) -> str:
    """
    Create the boot script for an IOC
    """
    with open(TEMPLATES / "st.cmd.jinja", "r") as f:
        template = Template(f.read())

    renderer = Render()

    return template.render(
        env_var_elements=renderer.render_environment_variable_elements(ioc_instance),
        script_elements=renderer.render_pre_ioc_init_elements(ioc_instance),
        post_ioc_init_elements=renderer.render_post_ioc_init_elements(ioc_instance),
    )
