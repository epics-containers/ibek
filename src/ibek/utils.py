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
        self.__reset__()

    def __reset__(self: "Utils"):
        """
        Reset all saved state. For use in testing where more than one
        IOC is rendered in a single session
        """
        self.variables: Dict[str, Any] = {}
        self.counters: Dict[str, Counter] = {}

    def set_var(self, key: str, value: Any):
        """create a global variable for our jinja context"""
        self.variables[key] = value

    def get_var(self, key: str) -> Any:
        """get the value a global variable for our jinja context"""
        # Intentionally raises a KeyError if the key doesn't exist
        return self.variables[key]

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


# a singleton Utility object for sharing state across all Entity renders
UTILS: Utils = Utils()
