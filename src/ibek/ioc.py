"""
Functions for generating an IocInstance derived class from a
support module definition YAML file
"""
from __future__ import annotations

import builtins
from typing import Any, Dict, Literal, Sequence, Tuple, Type, Union

from jinja2 import Template
from pydantic import Field, create_model, field_validator
from pydantic.fields import FieldInfo

from .globals import BaseSettings
from .support import Definition, IdArg, ObjectArg, Support
from .utils import UTILS

# A base class for applying settings to all serializable classes


id_to_entity: Dict[str, Entity] = {}


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

    # @model_validator(mode="before")  # type: ignore
    def add_ibek_attributes(cls, entity: Dict):
        """Add attributes used by ibek"""

        # add in the global __utils__ object for state sharing
        entity["__utils__"] = UTILS

        # copy 'values' from the definition into the Entity

        # if hasattr(entity, "__definition__"):
        #     entity.update(entity.__definition__.values)

        # Jinja expansion of any string args/values in the Entity's attributes
        for arg, value in entity.items():
            if isinstance(value, str):
                jinja_template = Template(value)
                entity[arg] = jinja_template.render(entity)
        return entity


def make_entity_model(definition: Definition, support: Support) -> Type[Entity]:
    """
    We can get a set of Definitions by deserializing an ibek
    support module definition YAML file.

    This function then creates an Entity derived class from each Definition.

    See :ref:`entities`
    """

    def add_entity(name, typ, description, default):
        entities[name] = (
            typ,
            FieldInfo(
                description=description,
                default=default,
            ),
        )

    entities: Dict[str, Tuple[type, Any]] = {}
    validators: Dict[str, Any] = {}

    # fully qualified name of the Entity class including support module
    full_name = f"{support.module}.{definition.name}"

    # add in each of the arguments as a Field in the Entity
    for arg in definition.args:
        full_arg_name = f"{full_name}.{arg.name}"

        if isinstance(arg, ObjectArg):

            @field_validator(arg.name)
            def lookup_instance(cls, id):
                try:
                    return id_to_entity[id]
                except KeyError:
                    raise KeyError(f"object id {id} not in {list(id_to_entity)}")

            validators[full_arg_name] = lookup_instance
            arg_type = str

        elif isinstance(arg, IdArg):

            @field_validator(arg.name)
            def save_instance(cls, id):
                if id in id_to_entity:
                    # TODO we are getting multiple registers of same Arg
                    pass  # raise KeyError(f"id {id} already defined in {list(id_to_entity)}")
                id_to_entity[id] = cls
                return id

            validators[full_arg_name] = save_instance
            arg_type = str

        else:
            # arg.type is str, int, float, etc.
            arg_type = getattr(builtins, arg.type)

        default = getattr(arg, "default", None)
        add_entity(arg.name, arg_type, arg.description, default)

    typ = Literal[full_name]  # type: ignore
    add_entity("type", typ, "The type of this entity", full_name)

    entity_cls = create_model(
        full_name.replace(".", "_"),
        **entities,
        __validators__=validators,
        # __base__=Entity,
    )  # type: ignore

    # add a link back to the Definition Object that generated this Entity Class
    entity_cls.__definition__ = definition

    return entity_cls


def make_entity_models(support: Support):
    """Create `Entity` subclasses for all `Definition` objects in the given
    `Support` instance.

    Then create a Pydantic model of an IOC class with its entities field
    set to a Union of all the Entity subclasses created."""

    entity_models = []
    entity_names = []

    for definition in support.defs:
        entity_models.append(make_entity_model(definition, support))
        if definition.name in entity_names:
            raise ValueError(f"Duplicate entity name {definition.name}")
        entity_names.append(definition.name)

    return entity_models


def make_ioc_model(entity_models: Sequence[Type[Entity]]) -> Type[IOC]:
    class NewIOC(IOC):
        entities: Sequence[Union[tuple(entity_models)]] = Field(  # type: ignore
            description="List of entities this IOC instantiates", default=()
        )

    return NewIOC


def clear_entity_model_ids():
    """Resets the global id_to_entity dict."""
    global id_to_entity

    id_to_entity.clear()


class IOC(BaseSettings):
    """
    Used to load an IOC instance entities yaml file into a Pydantic Model.
    """

    ioc_name: str = Field(description="Name of IOC instance")
    description: str = Field(description="Description of what the IOC does")
    generic_ioc_image: str = Field(
        description="The generic IOC container image registry URL"
    )
