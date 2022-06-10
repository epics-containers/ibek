"""
Functions for rendering lines in the boot script using Jinja2
"""

import sys
from dataclasses import asdict
from typing import Optional

from jinja2 import Template

from .ioc import IOC, Entity


def render_template_from_entity_attribute(
    instance: Entity, attribute: str
) -> Optional[str]:
    """
    Get the rendered template based on an instance attribute
    """
    attribute = getattr(instance.__definition__, attribute)
    if not attribute:
        return None
    all_lines = "\n".join(attribute)
    jinja_template = Template(all_lines)
    result = jinja_template.render(asdict(instance))
    return result


def render_script(instance: Entity) -> Optional[str]:
    """
    render the startup script by combining the jinja template from
    an entity with the arguments from an Entity
    """
    return render_template_from_entity_attribute(instance, "script")


def render_database(instance: Entity) -> Optional[str]:
    """
    render the lines required to instantiate database by combining the
    templates from the Entity's database list with the arguments from
    an Entity
    """
    templates = instance.__definition__.databases
    # The entity may not instantiate any database templates
    if not templates:
        return None
    jinja_txt = ""
    # include list entries expand to e.g. P={{ P }}
    jinja_arg = Template('{{ arg }}={{ "{{" + arg + "}}" }}')

    # TODO review need for Jinja in include args
    #   Jinja render define args then use fstring to combine
    for template in templates:
        db_file = template.file.strip("\n")
        db_args = template.define_args.splitlines()
        include_list = [
            jinja_arg.render({"arg": arg}) for arg in template.include_args or []
        ]
        db_arg_string = ", ".join(db_args + include_list)

        jinja_txt += (
            f'msi -I${{EPICS_DB_INCLUDE_PATH}} -M"{db_arg_string}" "{db_file}"\n'
        )

    jinja_template = Template(jinja_txt)
    db_txt = jinja_template.render(asdict(instance))

    # run the result through jinja again so we can refer to args for arg defaults
    # e.g.
    # - type: str
    #   name: VMAX
    #   description: Max Velocity (EGU/s)
    #   default: "{{VELO}}""
    db_template = Template(db_txt)
    db_txt = db_template.render(asdict(instance))

    return db_txt


def render_environment_variables(instance: Entity) -> Optional[str]:
    """
    render the environment variable elements by combining the jinja template
    from an entity with the arguments from an Entity
    """
    variables = getattr(instance.__definition__, "env_vars")
    if not variables:
        return None
    instance_as_dict = asdict(instance)
    env_var_txt = ""
    for variable in variables:
        # Substitute the name and value of the environment variable from args
        env_template = Template(f"epicsEnvSet \"{variable.name}\", '{variable.value}'")
        env_var_txt += env_template.render(instance_as_dict)
    return env_var_txt


def render_post_ioc_init(instance: Entity) -> Optional[str]:
    """
    render the post-iocInit entries by combining the jinja template
    from an entity with the arguments from an Entity
    """
    return render_template_from_entity_attribute(instance, "post_ioc_init")


def render_elements(ioc: IOC, element: str) -> str:
    """
    Render elements of a given IOC instance based on calling the correct method
    """
    method = getattr(sys.modules[__name__], element)
    elements = ""
    for instance in ioc.entities:
        if instance.entity_enabled:
            element = method(instance)
            if element:
                elements += element + "\n"
    return elements


def render_script_elements(ioc: IOC) -> str:
    """
    Render all of the startup script entries for a given IOC instance
    """
    return render_elements(ioc, "render_script")


def render_database_elements(ioc: IOC) -> str:
    """
    Render all of the DBLoadRecords entries for a given IOC instance
    """
    return render_elements(ioc, "render_database")


def render_environment_variable_elements(ioc: IOC) -> str:
    """
    Render all of the environment variable entries for a given IOC instance
    """
    return render_elements(ioc, "render_environment_variables")


def render_post_ioc_init_elements(ioc: IOC) -> str:
    """
    Render all of the post-iocInit elements for a given IOC instance
    """
    return render_elements(ioc, "render_post_ioc_init")
