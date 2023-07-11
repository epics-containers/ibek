"""
Functions for generating an IocInstance derived class from a
support module definition YAML file
"""
from __future__ import annotations

import builtins
import json
from typing import Any, Dict, Sequence, Tuple, Type, Union

from jinja2 import Template
from pydantic import Field, create_model
from typing_extensions import Literal

from .globals import BaseSettings, model_config
from .support import Definition, IdArg, ObjectArg, Support
from .utils import UTILS

# A base class for applying settings to all serializable classes


class Entity(BaseSettings):
    """
    A baseclass for all generated Entity classes. Provides the
    deserialize entry point.
    """

    # a link back to the Definition Object that generated this Definition
    __definition__: Definition

    entity_enabled: bool = Field(
        description="enable or disable this entity instance", default=True
    )

    def __post_init__(self: "Entity"):
        # If there is an argument which is an id then allow deserialization by that
        args = self.__definition__.args
        ids = set(a.name for a in args if isinstance(a, IdArg))
        assert len(ids) <= 1, f"Multiple id args {list(ids)} defined in {args}"
        if ids:
            # A string id, use that
            inst_id = getattr(self, ids.pop())
            assert inst_id not in id_to_entity, f"Already got an instance {inst_id}"
            id_to_entity[inst_id] = self

            # TODO - not working as printing own ID
            setattr(self, "__str__", inst_id)

        # add in the global __utils__ object for state sharing
        self.__utils__ = UTILS

        # copy 'values' from the definition into the Entity
        for value in self.__definition__.values:
            setattr(self, value.name, value.value)

        # Jinja expansion of any string args/values in the Entity's attributes
        for arg, value in self.__dict__.items():
            if isinstance(value, str):
                jinja_template = Template(value)
                rendered = jinja_template.render(self.__dict__)
                setattr(self, arg, rendered)


id_to_entity: Dict[str, Entity] = {}


def make_entity_model(definition: Definition, support: Support) -> Type[Entity]:
    """
    We can get a set of Definitions by deserializing an ibek
    support module definition YAML file.

    This function then creates an Entity derived class from each Definition.

    See :ref:`entities`
    """
    entities: Dict[str, Tuple[type, Any]] = {}

    # add in each of the arguments as a Field in the Entity
    for arg in definition.args:
        metadata: Any = None
        arg_type: Type

        if isinstance(arg, ObjectArg):
            pass  # TODO
            # def lookup_instance(id):
            #     try:
            #         return id_to_entity[id]
            #     except KeyError:
            #         raise ValidationError(f"{id} is not in {list(id_to_entity)}")

            # metadata = schema(extra={"vscode_ibek_plugin_type": "type_object"})
            # metadata = conversion(
            #     deserialization=Conversion(lookup_instance, str, Entity)
            # ) | schema(extra={"vscode_ibek_plugin_type": "type_object"})
            arg_type = Entity
        elif isinstance(arg, IdArg):
            arg_type = str
            # TODO
            # metadata = schema(extra={"vscode_ibek_plugin_type": "type_id"})
        else:
            # arg.type is str, int, float, etc.
            arg_type = getattr(builtins, arg.type)

        default = getattr(arg, "default", None)
        arg_field = Field(arg_type, description=arg.description)

        # TODO where does metadata go?
        # fld = Field(arg_type)

        entities[arg.name] = (arg_type, None)

    # put the literal name in as 'type' for this Entity this gives us
    # a unique key for each of the entity types we may instantiate
    full_name = f"{support.module}.{definition.name}"
    entities["type"] = (
        Literal[full_name],  # type: ignore
        full_name,
    )

    # entity_enabled controls rendering of the entity without having to delete it
    entities["entity_enabled"] = (bool, True)
    # add a link back to the Definition Object that generated this Definition
    # TODO
    # entities["__definition__"] = (Definition, None)

    entity_cls = create_model(
        "definitions",
        **entities,
        __config__=model_config,
    )  # type: ignore
    return entity_cls


def make_entity_models(support: Support):
    """Create `Entity` subclasses for all `Definition` objects in the given
    `Support` instance.

    Then create a Pydantic model of an IOC class with its entities field
    set to a Union of all the Entity subclasses created."""

    entity_models = []

    for definition in support.defs:
        entity_models.append(make_entity_model(definition, support))

    return entity_models


def clear_entity_classes():
    """Reset the modules namespaces, deserializers and caches of defined Entity
    subclasses"""

    # TODO: do we need this for Pydantic?


def make_ioc_model(entity_classes: Sequence[Type[Entity]]) -> str:
    class NewIOC(IOC):
        entities: Sequence[Union[tuple(entity_classes)]] = Field(  # type: ignore
            description="List of entities this IOC instantiates", default=()
        )

    return json.dumps(NewIOC.model_json_schema(), indent=2)


class IOC(BaseSettings):
    """
    Used to load an IOC instance entities yaml file into memory.

    This is the base class that is adjusted at runtime by updating the
    type of its entities attribute to be a union of all of the subclasses of Entity
    provided by the support module definitions used by the current IOC
    """

    ioc_name: str = Field(description="Name of IOC instance")
    description: str = Field(description="Description of what the IOC does")
    generic_ioc_image: str = Field(
        description="The generic IOC container image registry URL"
    )
    # placeholder for the entities attribute - updated at runtime
    entities: Sequence[Entity] = Field(
        description="List of entities this IOC instantiates"
    )
