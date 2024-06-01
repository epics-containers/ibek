"""
Classes to specify arguments to Definitions
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import Field
from typing_extensions import Literal

from .globals import BaseSettings


class Value(BaseSettings):
    """A calculated string value for a definition"""

    name: str = Field(description="Name of the value that the IOC instance will expose")
    description: str = Field(
        description="Description of what the value will be used for"
    )
    value: str = Field(description="The contents of the value")


class Arg(BaseSettings):
    """Base class for all Argument Types"""

    arg_type: str
    name: str = Field(
        description="Name of the argument that the IOC instance should pass"
    )
    description: str = Field(
        description="Description of what the argument will be used for"
    )


class ListArg(Arg):
    """An argument with a float value"""

    arg_type: Literal["list"] = "list"
    default: Optional[list] = None


class FloatArg(Arg):
    """An argument with a float value"""

    arg_type: Literal["float"] = "float"
    default: Optional[float] = None


class StrArg(Arg):
    """An argument with a str value"""

    arg_type: Literal["str"] = "str"
    default: Optional[str] = None


class IntArg(Arg):
    """An argument with an int value"""

    arg_type: Literal["int"] = "int"
    default: Optional[int] = None


class BoolArg(Arg):
    """An argument with an bool value"""

    arg_type: Literal["bool"] = "bool"
    default: Optional[bool] = None


class ObjectArg(Arg):
    """A reference to another entity defined in this IOC"""

    arg_type: Literal["object"] = "object"
    default: Optional[str] = None


class IdArg(Arg):
    """Explicit ID argument that an object can refer to"""

    arg_type: Literal["id"] = "id"
    default: Optional[str] = None


class EnumArg(Arg):
    """An argument with an enum value"""

    arg_type: Literal["enum"] = "enum"
    default: Optional[Any] = None

    values: Dict[str, Any] = Field(
        description="provides a list of values to make this argument an Enum",
    )
