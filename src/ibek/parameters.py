"""
Classes to specify arguments to Entity Models
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Optional

from pydantic import Field

from .globals import JINJA, BaseSettings

JinjaString = Annotated[
    str, Field(description="A Jinja2 template string", pattern=JINJA)
]


class DefineType(Enum):
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


class Define(BaseSettings):
    """A calculated value for an Entity Model"""

    description: str = Field(
        description="Description of what the value will be used for"
    )
    value: Any = Field(description="The contents of the value")
    type: DefineType | None = Field(
        description="The type of the value", default=DefineType.string
    )


class Param(BaseSettings):
    """Base class for all Argument Types"""

    type: str

    description: str = Field(
        description="Description of what the argument will be used for"
    )


class FloatParam(Param):
    """An argument with a float value"""

    type: Literal["float"] = "float"
    default: Optional[float | JinjaString] = None


class StrParam(Param):
    """An argument with a str value"""

    type: Literal["str"] = "str"
    default: Optional[str] = None


class IntParam(Param):
    """An argument with an int value"""

    type: Literal["int"] = "int"
    default: Optional[int | JinjaString] = None


class BoolParam(Param):
    """An argument with an bool value"""

    type: Literal["bool"] = "bool"
    default: Optional[bool | JinjaString] = None


class ObjectParam(Param):
    """A reference to another entity defined in this IOC"""

    type: Literal["object"] = "object"
    # represented by an id string in YAML but converted to an Entity object
    # during validation
    default: Optional[str | object] = None


class IdParam(Param):
    """Explicit ID argument that an object can refer to"""

    type: Literal["id"] = "id"
    default: Optional[str] = None


class EnumParam(Param):
    """An argument with an enum value"""

    type: Literal["enum"] = "enum"
    default: Optional[Any] = None

    values: dict[Any, Any] = Field(
        description="provides a list of values to make this argument an Enum",
    )


class DictParam(Param):
    """An argument with dict value"""

    type: Literal["dict"] = "dict"
    # represented yaml map or jinja ' | dict'
    default: Optional[dict | JinjaString] = None


class ListParam(Param):
    """An argument with list value"""

    type: Literal["list"] = "list"
    # represented yaml map or jinja ' | list'
    default: Optional[list | JinjaString] = None
