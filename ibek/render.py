"""
Functions for rendering lines in the boot script using Jinja2
"""

from dataclasses import asdict
from typing import TypeVar

from jinja2 import Template

from ibek.support import Entity, GenericIoc

T = TypeVar("T")


def render_script(instance: Entity) -> str:
    """
    render the startup script by combining the jinja template from
    an entity with the arguments from and Entity
    """
    all_lines = "\n".join(instance.entity.script)
    jinja_template = Template(all_lines)
    result = jinja_template.render(asdict(instance))
    return result


def render_database(instance: Entity) -> str:
    """
    render the lines required to instantiate database by combining the
    templates from the Entity's database list with the arguments from
    an Entity
    """
    templates = instance.entity.databases
    jinja_txt = ""

    for template in templates:
        db_file = template.file.strip("\n")
        db_args = template.define_args.strip("\n")
        jinja_txt += f'dbLoadRecords("{db_file}", ' f'"{db_args}")\n'

    jinja_template = Template(jinja_txt)
    db_txt = jinja_template.render(asdict(instance))

    return db_txt


def render_script_elements(ioc: GenericIoc) -> str:
    """
    Render all of the startup script entries for a given IOC instance
    """
    scripts = ""
    for instance in ioc.entities:
        scripts += render_script(instance) + "\n"
    return scripts


def render_database_elements(ioc: GenericIoc) -> str:
    """
    Render all of the DBLoadRecords entries for a given IOC instance
    """
    databases = ""
    for instance in ioc.entities:
        databases += render_database(instance) + "\n"
    return databases
