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
from .globals import BaseSettings
from .support import Definition
from .utils import UTILS

id_to_entity: Dict[str, Entity] = {}


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

    @model_validator(mode="after")  # type: ignore
    def add_ibek_attributes(cls, entity: Entity):
        """
        Whole Entity model validation
        """

        # find the id field in this Entity if it has one
        ids = {a.name for a in entity.__definition__.args if isinstance(a, IdArg)}

        entity_dict = entity.model_dump()
        for arg, value in entity_dict.items():
            if isinstance(value, str):
                # Jinja expansion of any of the Entity's string args/values
                value = UTILS.render(entity_dict, value)
                setattr(entity, arg, value)

            if arg in ids:
                # add this entity to the global id index
                if value in id_to_entity:
                    raise ValueError(f"Duplicate id {value} in {list(id_to_entity)}")
                id_to_entity[value] = entity
        return entity

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
