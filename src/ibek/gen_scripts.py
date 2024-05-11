"""
Functions for building the db and boot scripts
"""

import logging
import re
from typing import List, Tuple

from jinja2 import Template

from ibek.utils import UTILS

from .collection import CollectionDefinition
from .definition import Database
from .globals import TEMPLATES
from .ioc import Entity
from .render import Render
from .render_db import RenderDb

log = logging.getLogger(__name__)


def create_db_script(
    entities: List[Entity], extra_databases: List[Tuple[Database, Entity]]
) -> str:
    """
    Create make_db.sh script for expanding the database templates
    """
    with open(TEMPLATES / "ioc.subst.jinja", "r") as f:
        jinja_txt = f.read()

        renderer = RenderDb(entities)

        templates = renderer.render_database(extra_databases)

        return Template(jinja_txt).render(templates=templates)


def create_boot_script(entities: List[Entity]) -> str:
    """
    Create the boot script for an IOC
    """
    with open(TEMPLATES / "st.cmd.jinja", "r") as f:
        template = Template(f.read())

    renderer = Render()

    return template.render(
        __utils__=UTILS,
        env_var_elements=renderer.render_environment_variable_elements(entities),
        script_elements=renderer.render_pre_ioc_init_elements(entities),
        post_ioc_init_elements=renderer.render_post_ioc_init_elements(entities),
    )
