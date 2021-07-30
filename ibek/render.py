from dataclasses import asdict, dataclass
from typing import TypeVar

from jinja2 import Template

from ibek.support import EntityInstance

T = TypeVar("T")


@dataclass
class DatabaseEntry:
    """ Wrapper for database entries. """

    file: str
    define_args: str


def make_script(instance: EntityInstance) -> str:
    """
    render the startup script by combining the jinja template from
    an entity with the arguments from and EntityInstance
    """
    all_lines = "\n".join(instance.entity.script)
    jinja_template = Template(all_lines)
    result = jinja_template.render(asdict(instance))
    return result


def create_database(instance: EntityInstance) -> str:
    """
    render the lines required to instantiate database by combining the
    templates from the entity's database list with the arguments from
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
