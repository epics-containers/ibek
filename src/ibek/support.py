"""
The Support Class represents a deserialized <MODULE_NAME>.ibek.defs.yaml file.
It contains a hierarchy of Entity dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Type, Union

from apischema import Undefined, UndefinedType, deserialize, deserializer, identity
from apischema.conversions import Conversion
from typing_extensions import Annotated as A
from typing_extensions import Literal

from .globals import T, desc


@dataclass
class Arg:
    """Base class for all Argument Types"""

    name: A[str, desc("Name of the argument that the IOC instance should pass")]
    description: A[str, desc("Description of what the argument will be used for")]
    type: str
    default: Any

    # https://wyfo.github.io/apischema/latest/examples/subclass_union/
    def __init_subclass__(cls):
        # Deserializers stack directly as a Union
        deserializer(Conversion(identity, source=cls, target=Arg))


Default = A[
    Union[Optional[T], UndefinedType],
    desc("If given, and instance doesn't supply argument, what value should be used"),
]


# FloatArg must be defined before StrArg, otherwise we get:
#
#    TypeError: Invalid JSON type <class 'ruamel.yaml.scalarfloat.ScalarFloat'>
#
# During Support.deserialize, when default float values in pmac.ibek.defs.yaml do not
# have a trailing 'f'. It is due to the order of declaration of subclasses of
# Arg. When StrArg is before FloatArg, apischema attempts to deserialize as a
# string first. The coercion from str to number requires a trailing f if there
# is a decimal.
@dataclass
class FloatArg(Arg):
    """An argument with a float value"""

    type: Literal["float"] = "float"
    default: Default[float] = Undefined


@dataclass
class StrArg(Arg):
    """An argument with a str value"""

    type: Literal["str"] = "str"
    default: Default[str] = Undefined


@dataclass
class IntArg(Arg):
    """An argument with an int value"""

    type: Literal["int"] = "int"
    default: Default[int] = Undefined


@dataclass
class BoolArg(Arg):
    """An argument with an bool value"""

    type: Literal["bool"] = "bool"
    default: Default[bool] = Undefined


@dataclass
class ObjectArg(Arg):
    """A reference to another entity defined in this IOC"""

    type: Literal["object"] = "object"
    default: Default[str] = Undefined


@dataclass
class IdArg(Arg):
    """Explicit ID argument that an object can refer to"""

    type: Literal["id"] = "id"
    default: Default[str] = Undefined


@dataclass
class Database:
    """
    A database file that should be loaded by the startup script and its args
    """

    file: A[str, desc("Filename of the database template in <module_root>/db")]
    include_args: A[
        Sequence[str], desc("List of args to pass through to database")
    ] = ()
    define_args: A[str, desc("Arg string list to be generated as Jinja template")] = ""


@dataclass
class EnvironmentVariable:
    """
    An environment variable that should be set in the startup script
    """

    name: A[str, desc("Name of environment variable")]
    value: A[str, desc("Value to set")]


@dataclass
class Definition:
    """
    A single definition of a class of Entity that an IOC instance may instantiate
    """

    name: A[str, desc("Publish Definition as type <module>.<name> for IOC instances")]
    args: A[Sequence[Arg], desc("The arguments IOC instance should supply")] = ()
    databases: A[Sequence[Database], desc("Databases to instantiate")] = ()
    script: A[
        Sequence[str], desc("Startup script snippet defined as Jinja template")
    ] = ()
    env_vars: A[
        Sequence[EnvironmentVariable],
        desc("Environment variables to set in the boot script"),
    ] = ()
    post_ioc_init: A[
        Sequence[str], desc("Entries to add post iocInit(), such as dbpf")
    ] = ()


@dataclass
class Support:
    """
    Lists the definitions for a support module, this defines what Entities it supports

    Provides the deserialize entry point.
    """

    module: A[str, desc("Support module name, normally the repo name")]
    defs: A[
        Sequence[Definition],
        desc("The definitions an IOC can create using this module"),
    ]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)
