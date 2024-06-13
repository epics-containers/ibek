"""
Classes for generating an IocInstance derived class from a
support module definition YAML file
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, List, Sequence

from pydantic import (
    Field,
    model_validator,
)

from .definition import EntityDefinition
from .globals import BaseSettings
from .params import IdParam
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
    __definition__: EntityDefinition

    @model_validator(mode="after")
    def add_ibek_attributes(self):
        """
        Whole Entity model validation
        """

        # find the id field in this Entity if it has one
        ids = {
            name
            for name, value in self.__definition__.params.items()
            if isinstance(value, IdParam)
        }

        entity_dict = self.model_dump()
        for arg, value in entity_dict.items():
            model_field = self.model_fields[arg]

            if isinstance(value, str):
                # Jinja expansion of any of the Entity's string args/values
                value = UTILS.render(entity_dict, value)
                # this is a cheesy test - any better ideas please let me know
                if "Union" in str(model_field.annotation):
                    # Args that were non strings and have been rendered by Jinja
                    # must be coerced back into their original type
                    try:
                        # The following replace are to make the string json compatible
                        # (maybe we should python decode instead of json.loads)
                        value = value.replace("'", '"')
                        value = value.replace("True", "true")
                        value = value.replace("False", "false")
                        value = json.loads(value)
                    except:
                        print(
                            f"ERROR: fail to decode {value} as a {model_field.annotation}"
                        )
                        raise

            if model_field.annotation == object:
                # look up the actual object by it's id
                if isinstance(value, str):
                    value = get_entity_by_id(value)

            # update this entity instance with the rendered value
            setattr(self, arg, value)
            # update the entity_dict with the rendered value
            entity_dict[arg] = value

            if arg in ids:
                # add this entity to the global id index
                if value in id_to_entity:
                    raise ValueError(f"Duplicate id {value} in {list(id_to_entity)}")
                id_to_entity[value] = self

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
