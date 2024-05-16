"""
A class containing utility functions for passing into the Jinja context.

This allows us to provide simple functions that can be called inside
Jinja templates with {{ __utils__.function_name() }}. It also allows
us to maintain state between calls to the Jinja templates because
we pass a single instance of this class into all Jinja contexts.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

from jinja2 import Template


@dataclass
class Counter:
    """
    Provides the ability to supply unique numbers to Jinja templates
    """

    start: int
    current: int
    stop: int

    def increment(self, count: int):
        self.current += count
        if self.current > self.stop:
            raise ValueError(
                f"Counter {self.current} exceeded stop value of {self.stop}"
            )


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
        self.counters: Dict[str, Counter] = {}

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

    def set_var(self, key: str, value: Any):
        """create a global variable for our jinja context"""
        self.variables[key] = value

    def get_var(self, key: str) -> Any:
        """get the value a global variable for our jinja context"""
        return self.variables.get(key, "")

    def counter(
        self, name: str, start: int = 0, stop: int = 65535, inc: int = 1
    ) -> int:
        """
        get a named counter that increments by inc each time it is called

        creates a new counter if it does not yet exist
        """
        counter = self.counters.get(name)
        if counter is None:
            counter = Counter(start, start, stop)
            self.counters[name] = counter
        else:
            if counter.start != start or counter.stop != stop:
                raise ValueError(
                    f"Redefining counter {name} with different start/stop values"
                )
        result = counter.current
        counter.increment(inc)
        self.counters[name] = counter

        return result

    def render(self, context: Any, template_text: Any) -> str:
        """
        Render a Jinja template with the global __utils__ object in the context
        """
        if not isinstance(template_text, str):
            # because this function is used to template arguments, it may
            # be passed a non string which will always render to itself
            return template_text

        try:
            jinja_template = Template(template_text)
            return jinja_template.render(
                context,
                __utils__=self,
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
