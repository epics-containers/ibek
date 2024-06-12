"""
Classes to specify arguments to Definitions
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field
from typing_extensions import Annotated, Literal

from .globals import JINJA, BaseSettings

JinjaString = Annotated[
    str, Field(description="A Jinja2 template string", pattern=JINJA)
]


class ValueTypes(Enum):
    """The type of a value"""

    string = "str"
    float = "float"
    int = "int"
    bool = "bool"
    list = "list"

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self.value)


class Value(BaseSettings):
    """A calculated string value for a definition"""

    description: str = Field(
        description="Description of what the value will be used for"
    )
    value: Any = Field(description="The contents of the value")
    type: ValueTypes = Field(
        description="The type of the value", default=ValueTypes.string
    )


class Arg(BaseSettings):
    """Base class for all Argument Types"""

    type: str

    description: str = Field(
        description="Description of what the argument will be used for"
    )


class FloatArg(Arg):
    """An argument with a float value"""

    type: Literal["float"] = "float"
    default: Optional[float | JinjaString] = None


class StrArg(Arg):
    """An argument with a str value"""

    type: Literal["str"] = "str"
    default: Optional[str] = None


class IntArg(Arg):
    """An argument with an int value"""

    type: Literal["int"] = "int"
    default: Optional[int | JinjaString] = None


class BoolArg(Arg):
    """An argument with an bool value"""

    type: Literal["bool"] = "bool"
    default: Optional[bool | JinjaString] = None


class ObjectArg(Arg):
    """A reference to another entity defined in this IOC"""

    type: Literal["object"] = "object"
    # represented by an id string in YAML but converted to an Entity object
    # during validation
    default: Optional[str | object] = None


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
