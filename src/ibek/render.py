"""
Functions for rendering lines in the boot script using Jinja2
"""

from typing import Callable, List, Optional, Sequence, Union

from .entity_model import Comment, Script, Text, When
from .ioc import Entity
from .utils import UTILS


class Render:
    """
    A class for generating snippets of startup script / EPICS DB
    by using Jinja to combine snippet templates from support module
    yaml with substitution values supplied in ioc entity yaml
    """

    def __init__(self: "Render"):
        self.once_done: List[str] = []

    def render_text(
        self, instance: Entity, text: str, when=When.every, suffix=""
    ) -> str:
        """
        Add in the next line of text, honouring the once flag which will
        only add the line once per IOC.

        Jinja rendering of values/args has already been done in Entity.__post_init__
        but we pass all strings though jinja again to render any other jinja
        in the IOC (e.g. database and function entries)

        once uses the name of the model + suffix to track which lines
        have been rendered already. The suffix can be used where a given
        Entity has more than one element to render once (e.g. functions)
        """

        if when == When.first.value:
            name = instance._model.name + suffix
            if name not in self.once_done:
                self.once_done.append(name)
            else:
                return ""
        elif when == When.last.value:
            raise NotImplementedError("When.last not yet implemented")

        # Render Jinja entries in the text
        result = UTILS.render(instance, text)  # type: ignore

        if result == "":
            return ""

        return result + "\n"

    def render_script(self, instance: Entity, script_items: Script) -> Optional[str]:
        script = ""

        for item in script_items:
            if isinstance(item, Comment):
                comments = "\n".join(["# " + line for line in item.value.split("\n")])
                script += self.render_text(
                    instance, comments, item.when, suffix="comment"
                )
            elif isinstance(item, Text):
                script += self.render_text(
                    instance, item.value, item.when, suffix="text"
                )

        return script

    def render_pre_ioc_init(self, instance: Entity) -> Optional[str]:
        """
        render the startup script by combining the jinja template from
        an entity with the arguments from an Entity
        """
        pre_init = instance._model.pre_init
        return self.render_script(instance, pre_init)

    def render_post_ioc_init(self, instance: Entity) -> Optional[str]:
        """
        render the post-iocInit entries by combining the jinja template
        from an entity with the arguments from an Entity
        """
        post_init = instance._model.post_init
        return self.render_script(instance, post_init)

    def render_environment_variables(self, instance: Entity) -> Optional[str]:
        """
        render the environment variable elements by combining the jinja template
        from an entity with the arguments from an Entity
        """
        variables = getattr(instance._model, "env_vars")
        if not variables:
            return None

        env_var_txt = ""
        for variable in variables:
            # Substitute the name and value of the environment variable from args
            env_template = f"epicsEnvSet {variable.name} {variable.value}"
            env_var_txt += UTILS.render(
                instance,
                env_template,
            )  # type: ignore
        return env_var_txt + "\n"

    def render_elements(
        self,
        entities: Sequence[Entity],
        render_element: Callable[[Entity], Union[str, None]],
    ) -> str:
        """
        Render elements of a given IOC instance based on calling the correct method
        """
        elements = ""
        for entity in entities:
            if entity.entity_enabled:
                element = render_element(entity)
                if element:
                    elements += element
        return elements

    def render_pre_ioc_init_elements(self, entities: Sequence[Entity]) -> str:
        """
        Render all of the startup script entries for a given IOC instance
        """
        return self.render_elements(entities, self.render_pre_ioc_init)

    def render_post_ioc_init_elements(self, entities: Sequence[Entity]) -> str:
        """
        Render all of the post-iocInit elements for a given IOC instance
        """
        return self.render_elements(entities, self.render_post_ioc_init)

    def render_environment_variable_elements(self, entities: Sequence[Entity]) -> str:
        """
        Render all of the environment variable entries for a given IOC instance
        """
        return self.render_elements(entities, self.render_environment_variables)
