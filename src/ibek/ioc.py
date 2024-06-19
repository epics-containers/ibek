"""
Classes for generating an IocInstance derived class from a set of
support module YAML files
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

# a global dict of all entity instances indexed by their ID
id_to_entity: Dict[str, Entity] = {}


def get_entity_by_id(id: str) -> Entity:
    try:
        return id_to_entity[id]
    except KeyError:
        raise ValueError(f"object {id} not found in {list(id_to_entity)}")


def clear_entity_model_ids():
    """Resets the global id_to_entity dict"""

    id_to_entity.clear()


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
    _model: EntityModel

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
                value = get_entity_by_id(value)

        # If this field is not pre-existing, add it into the model instance.
        # This is how pre/post_defines are added.
        if name not in self.model_fields:
            self.model_fields[name] = FieldInfo(annotation=str, default=value)

        # update the model instance attribute with the rendered value
        setattr(self, name, value)

        if typ == "id":
            # add this entity to the global id index
            if value in id_to_entity:
                raise ValueError(f"Duplicate id {value} in {list(id_to_entity)}")
            id_to_entity[value] = self

    @model_validator(mode="after")
    def add_ibek_attributes(self):
        """
        Whole Entity model validation

        Do jinja rendering of pre_defines/ parameters / post_defines
        in the correct order.

        Also adds pre_defines and post_defines to the model instance, making
        them available for the phase 2 (final) jinja rendering performed in
        ibek.runtime_cmds.generate().
        """

        if self._model.pre_defines:
            for name, define in self._model.pre_defines.items():
                self._process_field(name, define.value, define.type)

        if self._model.parameters:
            for name, parameter in self._model.parameters.items():
                self._process_field(name, getattr(self, name), parameter.type)

        if self._model.post_defines:
            for name, define in self._model.post_defines.items():
                self._process_field(name, define.value, define.type)

        return self

    def __str__(self):
        """
        When a jinja template refers to an object by itself e.g.
            # this is the startup entry for {{ my_entity }}
        Jinja will attempt to render the object as a string and this
        method will be called.

        The behaviour is to print the ID of the object. Thus we look up
        which of our object's fields is the ID field and return the
        value of that field.
        """
        id_name = self._model._get_id_arg()
        if id_name:
            return getattr(self, id_name)
        else:
            raise ValueError(f"Entity {self} has no id field")

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
