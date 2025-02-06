"""
Functions for building the db and boot scripts
"""

import logging
from collections.abc import Sequence

from jinja2 import StrictUndefined, Template

from ibek.utils import UTILS

from .entity_model import Database
from .globals import TEMPLATES
from .ioc import Entity
from .render import Render
from .render_db import RenderDb

log = logging.getLogger(__name__)


def create_db_script(
    entities: Sequence[Entity], extra_databases: list[tuple[Database, Entity]]
) -> str:
    """
    Create make_db.sh script for expanding the database templates
    """
    with open(TEMPLATES / "ioc.subst.jinja") as f:
        jinja_txt = f.read()

        renderer = RenderDb(entities)

        templates = renderer.render_database(extra_databases)

        try:
            return Template(jinja_txt).render(
                templates=templates, undefined=StrictUndefined
            )
        except Exception:
            print(f"ERROR RENDERING DATABASE TEMPLATE:\n{templates}")
            raise


def create_boot_script(entities: Sequence[Entity]) -> str:
    """
    Create the boot script for an IOC
    """
    with open(TEMPLATES / "st.cmd.jinja") as f:
        template = Template(f.read())

    renderer = Render()

    return template.render(
        # global context for all jinja renders
        _global=UTILS,
        # put variables created with set/get directly in the context
        **UTILS.variables,
        env_var_elements=renderer.render_environment_variable_elements(entities),
        script_elements=renderer.render_pre_ioc_init_elements(entities),
        post_ioc_init_elements=renderer.render_post_ioc_init_elements(entities),
    )
