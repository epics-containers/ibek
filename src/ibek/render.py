"""
Functions for rendering lines in the boot script using Jinja2
"""

from typing import Callable, List, Optional, Sequence, Union

from jinja2 import Template

from .ioc import IOC, Entity
from .support import Comment, Function, When


class Render:
    """
    A class for generating snippets of startup script / EPICS DB
    by using Jinja to combine snippet templates from support module
    definition yaml with substitution values supplied in ioc entity yaml
    """

    def __init__(self: "Render"):
        self.once_done: List[str] = []

    def render_text(
        self, instance: Entity, text: str, when=When.every, suffix=""
    ) -> str:
        """
        Add in the next line of text, honouring the ``once`` flag which will
        only add the line once per IOC.

        Jinja rendering of values/args has already been done in Entity.__post_init__
        but we pass all strings though jinja again to render any other jinja
        in the IOC (e.g. database and function entries)

        ``once`` uses the name of the definition + suffix to track which lines
        have been rendered already. The suffix can be used where a given
        Entity has more than one element to render once (e.g. functions)
        """

        if when == When.first:
            name = instance.__definition__.name + suffix
            if name not in self.once_done:
                self.once_done.append(name)
            else:
                return ""
        elif when == When.last:
            raise NotImplementedError("When.last not yet implemented")

        # Render Jinja entries in the text
        jinja_template = Template(text)
        result = jinja_template.render(instance.__dict__)  # type: ignore

        if result == "":
            return ""

        return result + "\n"

    def render_function(self, instance: Entity, function: Function) -> str:
        """
        render a Function object that represents a function call in the IOC
        startup script
        """

        # initial function comment appears after newline for prettier formatting
        comment = f"\n# {function.name} "
        call = f"{function.name} "
        for name, value in function.args.items():
            comment += f"{name} "
            call += f"{value} "

        text = (
            self.render_text(
                instance, comment.strip(" "), when=When.first, suffix="func"
            )
            + self.render_text(
                instance, function.header, when=When.first, suffix="func_hdr"
            )
            + self.render_text(instance, call.strip(" "), when=function.when)
        )

        return text

    def render_script(
        self, instance: Entity, script_items: Sequence[Union[Function, Comment]]
    ) -> Optional[str]:
        script = ""

        for item in script_items:
            if isinstance(item, Comment):
                comments = "\n".join(["# " + line for line in item.value.split("\n")])
                script += self.render_text(
                    instance, comments, item.when, suffix="comment"
                )
            elif isinstance(item, Function):
                script += self.render_function(instance, item)

        return script

    def render_pre_ioc_init(self, instance: Entity) -> Optional[str]:
        """
        render the startup script by combining the jinja template from
        an entity with the arguments from an Entity
        """
        pre_init = instance.__definition__.pre_init
        return self.render_script(instance, pre_init)

    def render_post_ioc_init(self, instance: Entity) -> Optional[str]:
        """
        render the post-iocInit entries by combining the jinja template
        from an entity with the arguments from an Entity
        """
        post_init = instance.__definition__.post_init
        return self.render_script(instance, post_init)

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

            macros = []
            for arg, value in template.args.items():
                if value is None:
                    if arg not in instance.__dict__:
                        raise ValueError(
                            f"database arg '{arg}' in database template "
                            f"'{template.file}' not found in context"
                        )
                    macros.append(f"{arg}={{{{ {arg} }}}}")
                else:
                    macros.append(f"{arg}={value}")

            db_arg_string = ", ".join(macros)

            jinja_txt += (
                f'msi -I${{EPICS_DB_INCLUDE_PATH}} -M"{db_arg_string}" "{db_file}"\n'
            )

        jinja_template = Template(jinja_txt)
        db_txt = jinja_template.render(instance.__dict__)  # type: ignore

        return db_txt + "\n"

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
            env_var_txt += env_template.render(instance.__dict__)
        return env_var_txt + "\n"

    def render_elements(
        self, ioc: IOC, method: Callable[[Entity], Union[str, None]]
    ) -> str:
        """
        Render elements of a given IOC instance based on calling the correct method
        """
        elements = ""
        for instance in ioc.entities:
            if instance.entity_enabled:
                element = method(instance)
                if element:
                    elements += element
        return elements

    def render_pre_ioc_init_elements(self, ioc: IOC) -> str:
        """
        Render all of the startup script entries for a given IOC instance
        """
        return self.render_elements(ioc, self.render_pre_ioc_init)

    def render_post_ioc_init_elements(self, ioc: IOC) -> str:
        """
        Render all of the post-iocInit elements for a given IOC instance
        """
        return self.render_elements(ioc, self.render_post_ioc_init)

    def render_database_elements(self, ioc: IOC) -> str:
        """
        Render all of the DBLoadRecords entries for a given IOC instance
        """
        return self.render_elements(ioc, self.render_database)

    def render_environment_variable_elements(self, ioc: IOC) -> str:
        """
        Render all of the environment variable entries for a given IOC instance
        """
        return self.render_elements(ioc, self.render_environment_variables)
