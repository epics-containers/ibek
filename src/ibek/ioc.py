"""
Classes for generating an IocInstance derived class from a
support module definition YAML file
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Sequence

from pydantic import (
    Field,
    model_validator,
)

from .args import IdArg
from .definition import Definition
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
    """Resets the global id_to_entity dict. Used for testing."""

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
    __definition__: Definition

    @model_validator(mode="after")
    def add_ibek_attributes(self):
        """
        Whole Entity model validation
        """

        # find the id field in this Entity if it has one
        ids = {a.name for a in self.__definition__.args if isinstance(a, IdArg)}

        entity_dict = self.model_dump()
        for arg, value in entity_dict.items():
            if isinstance(value, str):
                # Jinja expansion of any of the Entity's string args/values
                value = UTILS.render(entity_dict, value)
                setattr(self, arg, value)

            if arg in ids:
                # add this entity to the global id index
                if value in id_to_entity:
                    raise ValueError(f"Duplicate id {value} in {list(id_to_entity)}")
                id_to_entity[value] = self

        # If an object field was populated by a default value it will currently
        # just be the object id. Now convert id into the actual object.
        for field in self.model_fields_set:
            prop = getattr(self, field)
            model_field = self.model_fields[field]

            if model_field.annotation == object:
                if isinstance(prop, str):
                    setattr(self, field, get_entity_by_id(prop))

        return self

    def __str__(self):
        # if this entity has an id then its string representation is the value of id
        id_name = self.__definition__._get_id_arg()
        return getattr(self, id_name) if id_name else super().__str__()


class IOC(BaseSettings):
    """
    Used to load an IOC instance entities yaml file into a Pydantic Model.
    """

    ioc_name: str = Field(description="Name of IOC instance")
    description: str = Field(description="Description of what the IOC does")
    entities: Sequence[Entity]
