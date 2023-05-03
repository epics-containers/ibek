"""
Functions for rendering lines in the boot script using Jinja2
"""

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from jinja2 import Template

from .ioc import IOC, Entity
from .support import Function, Once
from .utils import Utils


class Render:
    def __init__(self, utils: Utils):
        self.utils = utils
        self.once_done: List[str] = []

    def _to_dict(self, instance: Any) -> Dict[str, Any]:
        """
        Add the utils to the instance so we can use them in the jinja templates
        """
        result = asdict(instance)
        result["__utils__"] = self.utils

        return result

    def render_text(self, instance: Entity, text: str) -> str:
        """
        Get the rendered template based on an instance attribute
        """
        jinja_template = Template(text)
        result = jinja_template.render(self._to_dict(instance))  # type: ignore

        # run the result through jinja again so we can refer to args for arg defaults
        # e.g.
        #
        #   - type: str
        #     name: IPACid
        #     description: IPAC identifier
        #     default: "IPAC{{ slot }}"

        jinja_template = Template(result)
        result = jinja_template.render(self._to_dict(instance))  # type: ignore

        return result

    def render_script(self, instance: Entity) -> Optional[str]:
        """
        render the startup script by combining the jinja template from
        an entity with the arguments from an Entity
        """
        once: Optional[str] = None
        #     once = self.render_template_from_entity_attribute(instance, "script_once")
        #     self.once_done.append(instance.__definition__.name)

        script = ""
        script_items = getattr(instance.__definition__, "script")
        for line in script_items:
            if isinstance(line, str):
                script += self.render_text(instance, line) + "\n"
            elif isinstance(line, Once):
                if instance.__definition__.name not in self.once_done:
                    self.once_done.append(instance.__definition__.name)
                    script += self.render_text(instance, line.value) + "\n"
            elif isinstance(line, Function):
                pass

        if once and script:
            return once + "\n" + script
        else:
            return once or script

    def render_database(self, instance: Entity) -> Optional[str]:
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

        for template in templates:
            db_file = template.file.strip("\n")
            db_args = template.define_args.splitlines()
            include_list = [
                f"{arg}={{{{ {arg} }}}}" for arg in template.include_args or []
            ]
            db_arg_string = ", ".join(db_args + include_list)

            jinja_txt += (
                f'msi -I${{EPICS_DB_INCLUDE_PATH}} -M"{db_arg_string}" "{db_file}"\n'
            )

        jinja_template = Template(jinja_txt)
        db_txt = jinja_template.render(self._to_dict(instance))  # type: ignore

        # run the result through jinja again so we can refer to args for arg defaults

        db_template = Template(db_txt)
        db_txt = db_template.render(self._to_dict(instance))  # type: ignore

        return db_txt

    def render_environment_variables(self, instance: Entity) -> Optional[str]:
        """
        render the environment variable elements by combining the jinja template
        from an entity with the arguments from an Entity
        """
        variables = getattr(instance.__definition__, "env_vars")
        if not variables:
            return None

        env_var_txt = ""
        for variable in variables:
            # Substitute the name and value of the environment variable from args
            env_template = Template(f"epicsEnvSet {variable.name} {variable.value}")
            env_var_txt += env_template.render(self._to_dict(instance))
        return env_var_txt

    def render_post_ioc_init(self, instance: Entity) -> Optional[str]:
        """
        render the post-iocInit entries by combining the jinja template
        from an entity with the arguments from an Entity
        """
        script = ""
        for line in getattr(instance.__definition__, "post_ioc_init"):
            rendered_line = self.render_text(instance, line)
            script += rendered_line + "\n"

        return script

    def render_elements(self, ioc: IOC, element: str) -> str:
        """
        Render elements of a given IOC instance based on calling the correct method
        """
        method = getattr(self, element)
        elements = ""
        for instance in ioc.entities:
            if instance.entity_enabled:
                element = method(instance)
                if element:
                    elements += element + "\n"
        return elements

    def render_script_elements(self, ioc: IOC) -> str:
        """
        Render all of the startup script entries for a given IOC instance
        """
        return self.render_elements(ioc, "render_script")

    def render_database_elements(self, ioc: IOC) -> str:
        """
        Render all of the DBLoadRecords entries for a given IOC instance
        """
        return self.render_elements(ioc, "render_database")

    def render_environment_variable_elements(self, ioc: IOC) -> str:
        """
        Render all of the environment variable entries for a given IOC instance
        """
        return self.render_elements(ioc, "render_environment_variables")

    def render_post_ioc_init_elements(self, ioc: IOC) -> str:
        """
        Render all of the post-iocInit elements for a given IOC instance
        """
        return self.render_elements(ioc, "render_post_ioc_init")
