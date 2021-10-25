"""
Functions for rendering lines in the boot script using Jinja2
"""

from dataclasses import asdict
from typing import Optional

from jinja2 import Template

from .ioc import IOC, Entity


def render_script(instance: Entity) -> Optional[str]:
    """
    render the startup script by combining the jinja template from
    an entity with the arguments from an Entity
    """
    script = instance.__definition__.script
    if not script:
        return None
    all_lines = "\n".join(script)
    jinja_template = Template(all_lines)
    result = jinja_template.render(asdict(instance))
    return result


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

    for template in templates:
        db_file = template.file.strip("\n")
        db_args = template.define_args.strip("\n")
        if template.include_args:
            include_list = [
                jinja_arg.render({"arg": arg}) for arg in template.include_args
            ]
            db_args += ", " + ", ".join(include_list)

        jinja_txt += f'dbLoadRecords("{db_file}", ' f'"{db_args.strip(",")}")\n'

    jinja_template = Template(jinja_txt)
    db_txt = jinja_template.render(asdict(instance))

    return db_txt


def render_environment_variables(instance: Entity) -> Optional[str]:
    """
    render the environment variable elements by combining the jinja template
    from an entity with the arguments from an Entity
    """
    env_vars = instance.__definition__.env_vars
    if not env_vars:
        return None
    all_lines = "\n".join(env_vars)
    jinja_template = Template(all_lines)
    result = jinja_template.render(asdict(instance))
    return result


def render_post_ioc_init(instance: Entity) -> Optional[str]:
    """
    render the post-iocInit entries by combining the jinja template
    from an entity with the arguments from an Entity
    """
    entries = instance.__definition__.post_ioc_init
    if not entries:
        return None
    all_lines = "\n".join(entries)
    jinja_template = Template(all_lines)
    result = jinja_template.render(asdict(instance))
    return result


def render_script_elements(ioc: IOC) -> str:
    """
    Render all of the startup script entries for a given IOC instance
    """
    scripts = ""
    for instance in ioc.entities:
        script = render_script(instance)
        if script:
            scripts += script + "\n"
    return scripts


def render_database_elements(ioc: IOC) -> str:
    """
    Render all of the DBLoadRecords entries for a given IOC instance
    """
    databases = ""
    for instance in ioc.entities:
        database = render_database(instance)
        if database:
            databases += database + "\n"
    return databases


def render_environment_variable_elements(ioc: IOC) -> str:
    """
    Render all of the environment variable entries for a given IOC instance
    """
    env_var_elements = ""
    for instance in ioc.entities:
        element = render_environment_variables(instance)
        if element:
            env_var_elements += element + "\n"
    return env_var_elements


def render_post_ioc_init_elements(ioc: IOC) -> str:
    """
    Render all of the post-iocInit elements for a given IOC instance
    """
    post_ioc_init_elements = ""
    for instance in ioc.entities:
        element = render_post_ioc_init(instance)
        if element:
            post_ioc_init_elements += element + "\n"
    return post_ioc_init_elements
