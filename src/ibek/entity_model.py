"""
The EntityModel class describes what a given support module can instantiate.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Mapping, Optional, Sequence, Union

from pydantic import Field, PydanticUndefinedAnnotation
from typing_extensions import Literal

from .globals import BaseSettings
from .parameters import Define, IdParam, Param
from .sub_entity import SubEntity


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


class Database(BaseSettings):
    """
    A database file that should be loaded by the startup script and its args
    """

    file: str = Field(
        description="Filename of the database template in <module_root>/db"
    )

    enabled: str = Field(
        description="Set to False to disable loading this database", default="True"
    )

    args: Mapping[str, Optional[str]] = Field(
        description=(
            "Dictionary of args and values to pass through to database. "
            "A value of None is equivalent to ARG: '{{ ARG }}'. "
            "See `UTILS.render_map` for more details."
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


Script = Sequence[Union[Text, Comment]]


class EntityPVI(BaseSettings):
    """Entity PVI definition"""

    yaml_path: str = Field(
        description="Path to .pvi.device.yaml - absolute or relative to PVI_DEFS"
    )
    ui_index: bool = Field(
        True,
        description="Whether to add the UI to the IOC index.",
    )
    ui_macros: dict[str, str | None] = Field(
        None,
        description=(
            "Macros to launch the UI on the IOC index. "
            "These must be args of the Entity this is attached to."
        ),
    )
    pv: bool = Field(
        False,
        description=(
            "Whether to generate a PVI PV. This adds a database template with info "
            "tags that create a PVAccess PV representing the device structure."
        ),
    )
    pv_prefix: str = Field("", description='PV prefix for PVI PV - e.g. "$(P)"')


discriminated = Annotated[  # type: ignore
    Union[tuple(Param.__subclasses__())],
    Field(discriminator="type", description="union of arg types"),
]


class EntityModel(BaseSettings):
    """
    A Model for a class of Entity that an IOC instance may instantiate
    """

    name: str = Field(
        description="Publish EntityModel as type <module>.<name> for IOC instances"
    )
    description: str = Field(
        description="A description of the Support module defined here"
    )
    pre_defines: dict[str, Define] = Field(
        description="Calculated values to use as additional arguments "
        "With Jinja evaluation before all Args",
        default=(),
    )
    # declare Arg as Union of its subclasses for Pydantic to be able to deserialize
    parameters: dict[str, discriminated] = Field(  # type: ignore
        description="The arguments IOC instance should supply",
        default=(),
    )
    post_defines: dict[str, Define] = Field(
        description="Calculated values to use as additional arguments "
        "With Jinja evaluation after all Args",
        default=(),
    )
    pre_init: Script = Field(
        description="Startup script snippets to add before iocInit()", default=()
    )
    post_init: Script = Field(
        description="Startup script snippets to add post iocInit(), such as dbpf",
        default=(),
    )
    databases: Sequence[Database] = Field(
        description="Databases to instantiate", default=[]
    )
    env_vars: Sequence[EnvironmentVariable] = Field(
        description="Environment variables to set in the boot script", default=()
    )
    pvi: Optional[EntityPVI] = Field(
        description="PVI definition for Entity", default=None
    )

    # list of additional entities to instantiate for each instance of this definition
    sub_entities: Sequence[SubEntity] = Field(
        description="The sub-entity instances that this collection is to instantiate",
        default=(),
    )

    shared: Sequence[Any] = Field(
        description="A place to create any anchors required for repeating YAML",
        default=(),
    )

    def _get_id_arg(self) -> str | None:
        """
        Lookup which of this object's fields represents its ID. The ID is the
        field of type IdParam whose value is the identifying name for
        this object.

        The jinja templates of other objects can refer to this object by the
        value of its ID field.
        """
        for name, param in self.parameters.items():
            if isinstance(param, IdParam):
                return name
        return None
