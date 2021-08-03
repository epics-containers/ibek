from dataclasses import asdict
from typing import TypeVar

from jinja2 import Template

from ibek.support import EntityInstance

T = TypeVar("T")


def render_script(instance: EntityInstance) -> str:
    """
    render the startup script by combining the jinja template from
    an entity with the arguments from and EntityInstance
    """
    all_lines = "\n".join(instance.entity.script)
    jinja_template = Template(all_lines)
    result = jinja_template.render(asdict(instance))
    return result


def render_database(instance: EntityInstance) -> str:
    """
    render the lines required to instantiate database by combining the
    templates from the Entity's database list with the arguments from
    an EntityInstance
    """
    templates = instance.entity.databases
    jinja_txt = ""

    for template in templates:
        jinja_txt += (
            f"dbLoadRecords(\"{template.__dict__['file']}\", "
            f"\"{template.__dict__['define_args']}\")\n"
        )

    jinja_template = Template(jinja_txt)
    db_txt = jinja_template.render(asdict(instance))

    return db_txt


def render_script_elements(entity_instances) -> str:
    scripts = ""
    for instance in entity_instances.instances:
        scripts += render_script(instance) + "\n"
    return scripts


def render_database_elements(entity_instances) -> str:
    databases = ""
    for instance in entity_instances.instances:
        databases += render_database(instance) + "\n"
    return databases
