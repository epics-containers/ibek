"""
Classes for generating an IocInstance derived class from a
support module definition YAML file
"""

from __future__ import annotations

import builtins
import json
from collections import OrderedDict
from enum import Enum
from typing import Any, Dict, List, Sequence

from pydantic import (
    ConfigDict,
    Field,
    model_validator,
)
from pydantic.fields import FieldInfo

from .entity_model import EntityModel
from .globals import BaseSettings
from .params import Define, IdParam
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
    __definition__: EntityModel

    def _process_field(
        self: Entity, name: str, typ: str, value: Any, ids: list[str]
    ) -> Any:
        """
        Process an Entitiy field - doing jinja rendering and type coercion as required
        """

        if isinstance(value, str):
            # Jinja expansion always performed on string fields
            value = UTILS.render(self, value)
            # TODO this is a cheesy test - any better ideas please let me know
            if "Union" in str(typ):
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
                    print(f"ERROR: fail to decode {value} as a {typ}")
                    raise

        if typ == object:
            # look up the actual object by it's id
            if isinstance(value, str):
                value = get_entity_by_id(value)

        # pre/post_defines are added into the model instance fields list here
        if name not in self.model_fields:
            self.model_fields[name] = FieldInfo(annotation=type(typ), default=value)

        # update the attribute with the rendered value
        setattr(self, name, value)

        if name in ids:
            # add this entity to the global id index
            if value in id_to_entity:
                raise ValueError(f"Duplicate id {value} in {list(id_to_entity)}")
            id_to_entity[value] = self

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

        # Do jinja rendering of pre_defines/ parameters / post_defines
        # in the correct order. _process_parameter also adds the pre/post_defines
        # into the model instance itself so that they are available later in the
        # second phase of jinja rendering for pre_init, post_init and databases.

        for name, define in self.__definition__.pre_defines.items():
            self._process_field(name, define.value, define.type, ids)

        for name, parameter in self.model_dump().items():
            typ = self.model_fields[name].annotation
            self._process_field(name, parameter, typ, ids)

        for name, define in self.__definition__.post_defines.items():
            self._process_field(name, define.value, define.type, ids)

        # we have updated the model with jinja rendered values and also with
        # pre/post_defines so allow extras and rebuild the model
        self.model_config["extra"] = "allow"
        self.model_rebuild(force=True)

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
