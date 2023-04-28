"""
A class containing utility functions for passing into the Jinja context.

This allows us to provide simple functions that can be called inside
Jinja templates with {{ __utils__.function_name() }}. It also allows
us to maintain state between calls to the Jinja templates because
we pass a single instance of this class into all Jinja contexts.
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Counter:
    start: int
    current: int
    stop: int

    def increment(self):
        self.current += 1
        if self.current > self.stop:
            raise ValueError(
                f"Counter {self.current} exceeded stop value of {self.stop}"
            )


class Utils:
    def __init__(self, ioc_name: str):
        self.ioc_name = ioc_name
        self.variables: Dict[str, Any] = {}
        self.counters: Dict[str, Counter] = {}

    def set_var(self, key: str, value: Any):
        """create a global variable for our jinja context"""
        self.variables[key] = value

    def get_var(self, key: str) -> Any:
        """get the value a global variable for our jinja context"""
        # Intentionally raises a KeyError if the key doesn't exist
        return self.variables[key]

    def counter(self, name: str, start: int = 0, stop: int = 65535) -> int:
        """
        get a named counter that increments each time it is called

        creates a new counter if it does not yet exist
        """
        counter = self.counters.get(name, Counter(start, start, stop))
        result = counter.current
        counter.increment()
        self.counters[name] = counter

        return result
