"""
A class containing utility functions for passing into the Jinja context.

This allows us to provide simple functions that can be called inside
Jinja templates with {{ _global.function_name() }}. It also allows
us to maintain state between calls to the Jinja templates because
we pass a single instance of this class into all Jinja contexts.
"""

import os
from pathlib import Path
from typing import Any, Dict, Mapping

from jinja2 import StrictUndefined, Template


class Utils:
    """
    A Utility class for adding functions to the Jinja context
    """

    def __init__(self: "Utils"):
        self.file_name: str = ""
        self.ioc_name: str = ""
        self.__reset__()

    def __reset__(self: "Utils"):
        """
        Reset all saved state. For use in testing where more than one
        IOC is rendered in a single session
        """
        self.variables: Dict[str, Any] = {}

    def set_file_name(self: "Utils", file: Path):
        """
        Set the ioc name based on the file name of the instance definition
        """
        self.file_name = file.stem

    def set_ioc_name(self: "Utils", name: str):
        """
        Set the ioc name based on the file name of the instance definition
        """
        self.ioc_name = name

    def get_env(self, key: str) -> str:
        """
        Get an environment variable
        """
        return os.environ.get(key, "")

    def set(self, key: str, value: Any) -> Any:
        """create a global variable for our jinja context"""
        s_key = str(key)
        self.variables[s_key] = value
        return value

    def get(self, key: str, default="") -> Any:
        """get the value a global variable for our jinja context"""
        # default is used to set an initial value if the variable is not set
        s_key = str(key)
        return self.variables.get(s_key, default)

    def incrementor(
        self, name: str, start: int = 0, increment: int = 1, stop: int | None = None
    ) -> int:
        """
        get a named counter that increments by inc each time it is called

        creates a new counter if it does not yet exist
        """
        index = str(name)
        counter = self.variables.get(index)

        if counter is None:
            self.variables[index] = start
        else:
            if not isinstance(counter, int):
                raise ValueError(f"Variable {index} is not an integer")
            self.variables[index] += increment
            if stop is not None and self.variables[index] > stop:
                raise ValueError(f"Counter {index} exceeded maximum value of {stop}")

        return self.variables[index]

    def render(self, context: Any, template_text: Any) -> str:
        """
        Render a Jinja template with the global _global object in the context
        """
        if not isinstance(template_text, str):
            # because this function is used to template arguments, it may
            # be passed a non string which will always render to itself
            return template_text

        try:
            jinja_template = Template(template_text, undefined=StrictUndefined)
            return jinja_template.render(
                context,
                # global context for all jinja renders
                _global=self,
                # put variables created with set/get directly in the context
                **self.variables,
                ioc_yaml_file_name=self.file_name,
                ioc_name=self.ioc_name,
            )
        except Exception:
            print(f"ERROR RENDERING TEMPLATE:\n{template_text}")
            raise

    def render_map(self, context: Any, map: Mapping[str, str | None]) -> dict[str, str]:
        """
        Render a map of jinja templates with values from the given context.

        If given a key with a value of `None`, the key itself will be used as a template
        value, so ``{"P": None}`` is equivalent to ``{"P": "{{ P }}"}``.

        Args:
            context: Context to extract template variables from
            map: Map of macro to jinja template to render

        """
        return {
            key: self.render(
                context, template if template is not None else "{{ %s }}" % key
            )
            for key, template in map.items()
        }


# a singleton Utility object for sharing state across all Entity renders
UTILS: Utils = Utils()
