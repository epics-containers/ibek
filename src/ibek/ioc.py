"""
Classes for generating an IocInstance derived class from a
support module definition YAML file
"""

from __future__ import annotations

import ast
import builtins
from enum import Enum
from typing import Any, Dict, List, Sequence

from pydantic import (
    Field,
    model_validator,
)
from pydantic.fields import FieldInfo

from .entity_model import EntityModel
from .globals import BaseSettings
from .utils import UTILS


class EnumVal(Enum):
    """
    An enum that is printed as its name only
    """

    def __str__(self):
        return self.name


class Entity(BaseSettings):
    """
    A baseclass for all generated Entity classes.
    """

    type: str = Field(description="The type of this entity")
    entity_enabled: bool = Field(
        description="enable or disable this entity instance", default=True
    )
    __definition__: EntityModel

    def __init__(self, **data):
        super().__init__(**data)
        self.__id_to_entity = {}

    def get_entity_by_id(self, id: str) -> Entity:
        try:
            return self.__id_to_entity[id]
        except KeyError:
            raise ValueError(f"object {id} not found in {list(self.__id_to_entity)}")

    def _process_field(self: Entity, name: str, value: Any, typ: str):
        """
        Process an Entity field - doing jinja rendering, type coercion and
        object id storage/lookup as required.
        """

        if isinstance(value, str):
            # Jinja expansion always performed on string fields
            value = UTILS.render(self, value)
            if typ in ["list", "int", "float", "bool"]:
                # coerce the rendered parameter to its intended type
                try:
                    cast_type = getattr(builtins, typ)
                    value = cast_type(ast.literal_eval(value))
                except:
                    print(f"ERROR: decoding field '{name}', value '{value}' as {typ}")
                    raise

        if typ == "object":
            # look up the actual object by it's id
            if isinstance(value, str):
                value = self.get_entity_by_id(value)

        # If this field is not pre-existing, add it into the model instance.
        # This is how pre/post_defines are added.
        if name not in self.model_fields:
            self.model_fields[name] = FieldInfo(annotation=str, default=value)

        # update the model instance attribute with the rendered value
        setattr(self, name, value)

        if typ == "id":
            # add this entity to the global id index
            if value in self.__id_to_entity:
                raise ValueError(f"Duplicate id {value} in {list(self.__id_to_entity)}")
            self.__id_to_entity[value] = self

    @model_validator(mode="after")
    def add_ibek_attributes(self):
        """
        Whole Entity model validation

        Do jinja rendering of pre_defines/ parameters / post_defines
        in the correct order.

        Also adds  pre_define and post_defines to the model instance, making
        them available for the phase 2 (final) jinja rendering performed in
        ibek.runtime_cmds.generate().
        """

        if self.__definition__.pre_defines:
            for name, define in self.__definition__.pre_defines.items():
                self._process_field(name, define.value, define.type)

        if self.__definition__.params:
            for name, parameter in self.__definition__.params.items():
                self._process_field(name, getattr(self, name), parameter.type)

        if self.__definition__.post_defines:
            for name, define in self.__definition__.post_defines.items():
                self._process_field(name, define.value, define.type)

        return self

    def __str__(self):
        # if this entity has an id then its string representation is the value of id
        id_name = self.__definition__._get_id_arg()
        return getattr(self, id_name) if id_name else super().__str__()

    def __repr__(self):
        return str(self)


class IOC(BaseSettings):
    """
    Used to load an IOC instance entities yaml file into a Pydantic Model.
    """

    ioc_name: str = Field(description="Name of IOC instance")
    description: str = Field(description="Description of what the IOC does")
    entities: List[Entity]
    shared: Sequence[Any] = Field(
        description="A place to create any anchors required for repeating YAML",
        default=(),
    )

    # a dict of all entity instances in this IOC, indexed by their ID
    __id_to_entity: Dict[str, Entity]
