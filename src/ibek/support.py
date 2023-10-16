"""
The Support Class represents a deserialized <MODULE_NAME>.ibek.support.yaml file.
"""
from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Sequence, Union

from pydantic import Field, PydanticUndefinedAnnotation
from typing_extensions import Literal

from .globals import BaseSettings


def default(T: type):
    """
    defines a default type which may be
    """
    return Field(
        Union[Optional[T], PydanticUndefinedAnnotation],
        description="If given, instance doesn't supply argument, what value should be used",
    )


class When(Enum):
    first = "first"
    every = "every"
    last = "last"


class Arg(BaseSettings):
    """Base class for all Argument Types"""

    type: str
    name: str = Field(
        description="Name of the argument that the IOC instance should pass"
    )
    description: str = Field(
        description="Description of what the argument will be used for"
    )


class FloatArg(Arg):
    """An argument with a float value"""

    type: Literal["float"] = "float"
    default: Optional[float] = None


class StrArg(Arg):
    """An argument with a str value"""

    type: Literal["str"] = "str"
    default: Optional[str] = None


class IntArg(Arg):
    """An argument with an int value"""

    type: Literal["int"] = "int"
    default: Optional[int] = None


class BoolArg(Arg):
    """An argument with an bool value"""

    type: Literal["bool"] = "bool"
    default: Optional[bool] = None


class ObjectArg(Arg):
    """A reference to another entity defined in this IOC"""

    type: Literal["object"] = "object"
    default: Optional[str] = None


class IdArg(Arg):
    """Explicit ID argument that an object can refer to"""

    type: Literal["id"] = "id"
    default: Optional[str] = None


class EnumArg(Arg):
    """An argument with an enum value"""

    type: Literal["enum"] = "enum"
    default: Optional[Any] = None

    values: Dict[str, Any] = Field(
        description="provides a list of values to make this argument an Enum",
    )


class Database(BaseSettings):
    """
    A database file that should be loaded by the startup script and its args
    """

    file: str = Field(
        description="Filename of the database template in <module_root>/db"
    )

    args: Mapping[str, Optional[str]] = Field(
        description=(
            "Dictionary of args and values to pass through to database. "
            "A value of None is equivalent to ARG: '{{ ARG }}'"
        )
    )


class EnvironmentVariable(BaseSettings):
    """
    An environment variable that should be set in the startup script
    """

    name: str = Field(description="Name of environment variable")
    value: str = Field(description="Value to set")


class Comment(BaseSettings):
    """
    A script snippet that will have '# ' prepended to every line
    for insertion into the startup script
    """

    type: Literal["comment"] = "comment"
    when: When = Field(description="One of first / every / last", default="every")
    value: str = Field(
        description="A comment to add into the startup script", default=""
    )


class Text(BaseSettings):
    """
    A script snippet to insert into the startup script
    """

    type: Literal["text"] = "text"
    when: str = Field(description="One of first / every / last", default="every")
    value: str = Field(description="raw text to add to the startup script", default="")


class Value(BaseSettings):
    """A calculated string value for a definition"""

    name: str = Field(description="Name of the value that the IOC instance will expose")
    description: str = Field(
        description="Description of what the value will be used for"
    )
    value: str = Field(description="The contents of the value")


Script = Sequence[Union[Text, Comment]]


class EntityPVI(BaseSettings):
    """Entity PVI definition"""

    yaml_path: str = Field(
        description="Path to .pvi.device.yaml - absolute or relative to PVI_DEFS"
    )
    index: bool = Field(
        description="Whether to add generated UI to index for Entity", default=True
    )
    prefix: str = Field(description="PV prefix to pass as $(prefix) on index button")
    pva: bool = Field(
        description="Whether to generate PVA structure template", default=False
    )


class Definition(BaseSettings):
    """
    A single definition of a class of Entity that an IOC instance may instantiate
    """

    name: str = Field(
        description="Publish Definition as type <module>.<name> for IOC instances"
    )
    description: str = Field(
        description="A description of the Support module defined here"
    )
    # declare Arg as Union of its subclasses for Pydantic to be able to deserialize
    args: Sequence[Union[tuple(Arg.__subclasses__())]] = Field(  # type: ignore
        description="The arguments IOC instance should supply", default=()
    )
    values: Sequence[Value] = Field(
        description="The values IOC instance should supply", default=()
    )
    databases: Sequence[Database] = Field(
        description="Databases to instantiate", default=[]
    )
    pre_init: Script = Field(
        description="Startup script snippets to add before iocInit()", default=()
    )
    post_init: Script = Field(
        description="Startup script snippets to add post iocInit(), such as dbpf",
        default=(),
    )
    env_vars: Sequence[EnvironmentVariable] = Field(
        description="Environment variables to set in the boot script", default=()
    )
    pvi: EntityPVI = Field(description="PVI definition for Entity", default=None)

    def _get_id_arg(self):
        """Returns the name of the ID argument for this definition, if it exists"""
        for arg in self.args:
            if isinstance(arg, IdArg):
                return arg.name


class Support(BaseSettings):
    """
    Lists the definitions for a support module, this defines what Entities it supports

    Provides the deserialize entry point.
    """

    module: str = Field(description="Support module name, normally the repo name")
    defs: Sequence[Definition] = Field(
        description="The definitions an IOC can create using this module"
    )

    @classmethod
    def get_schema(cls):
        return json.dumps(cls.model_json_schema(), indent=2)
