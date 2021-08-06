"""
Classes used to define the arguments available to Entities in ioc instance
entity files
"""
from dataclasses import dataclass
from typing import Any, Optional, TypeVar, Union

from apischema import Undefined, UndefinedType, deserializer, schema
from apischema.conversions import Conversion, identity
from typing_extensions import Annotated as A
from typing_extensions import Literal

T = TypeVar("T")


def desc(description: str):
    return schema(description=description)


@dataclass
class Arg:
    """Base class for all Argument Types"""

    name: A[str, desc("Name of the argument that the IOC instance should pass")]
    description: A[str, desc("Description of what the argument will be used for")]
    type: str
    default: Any

    # https://wyfo.github.io/apischema/examples/subclass_union/
    def __init_subclass__(cls):
        # Deserializers stack directly as a Union
        deserializer(Conversion(identity, source=cls, target=Arg))


Default = A[
    Union[Optional[T], UndefinedType],
    desc("If given, and instance doesn't supply argument, what value should be used"),
]


@dataclass
class StrArg(Arg):
    """An argument with a str value"""

    type: Literal["str"] = "str"
    default: Default[str] = Undefined
    is_id: A[
        bool, desc("If true, instances may refer to this instance by this arg")
    ] = False


@dataclass
class IntArg(Arg):
    """An argument with an int value"""

    type: Literal["int"] = "int"
    default: Default[Union[int, str]] = Undefined


@dataclass
class FloatArg(Arg):
    """An argument with a float value"""

    type: Literal["float"] = "float"
    # FloatArg defaults always look like str of the form "0.5f"
    default: Default[Union[float, str]] = Undefined

    # Strip the trailing f so that the string resolves to a float for EPICS
    def __post_init__(self):
        if isinstance(self.default, str):
            if self.default.endswith("f"):
                self.default = self.default[:-1]


@dataclass
class ObjectArg(Arg):
    """A reference to another entity defined in this IOC"""

    type: A[str, desc("Entity class, <module>.<entity_name>")]
    default: Default[str] = Undefined
