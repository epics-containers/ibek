"""
A class for constructing Entity classes from Definitions
"""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any, Dict, List, Literal, Tuple, Type

from pydantic import create_model, field_validator
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from ruamel.yaml.main import YAML

from .args import EnumArg, IdArg, ObjectArg
from .ioc import Entity, EnumVal, clear_entity_model_ids, get_entity_by_id
from .support import EntityDefinition, Support
from .utils import UTILS


class EntityFactory:
    def __init__(self) -> None:
        """
        A class to create `Entity` models from `EntityDefinition`s.

        Created models are stored in `self._entity_models` to lookup when resolving nested `SubEntity`s.
        """
        self._entity_models: Dict[str, Type[Entity]] = {}
        # starting a new EntityFactory implies we should throw away any existing
        # Entity instances - this is required for tests which create multiple
        # EntityFactories
        clear_entity_model_ids()

    def make_entity_models(self, definition_yaml: List[Path]) -> List[Type[Entity]]:
        """
        Read a set of *.ibek.support.yaml files and generate Entity classes
        from their Definition entries
        """

        for definition in definition_yaml:
            support_dict = YAML(typ="safe").load(definition)

            Support.model_validate(support_dict)

            # deserialize the support module definition file
            support = Support(**support_dict)
            # make Entity classes described in the support module definition file
            self._make_entity_models(support)

        return list(self._entity_models.values())

    def _make_entity_model(
        self, definition: EntityDefinition, support: Support
    ) -> Type[Entity]:
        """
        Create an Entity Model from a Definition instance and a Support instance.
        """

        def add_arg(name, typ, description, default):
            if default is None:
                default = PydanticUndefined
            args[name] = (
                typ,
                FieldInfo(description=description, default=default),
            )

        args: Dict[str, Tuple[type, Any]] = {}
        validators: Dict[str, Any] = {}

        # fully qualified name of the Entity class including support module
        full_name = f"{support.module}.{definition.name}"

        # add in each of the arguments as a Field in the Entity
        for arg in definition.args:
            full_arg_name = f"{full_name}.{arg.name}"
            arg_type: Any

            if isinstance(arg, ObjectArg):

                @field_validator(arg.name, mode="after")
                def lookup_instance(cls, id):
                    return get_entity_by_id(id)

                validators[full_arg_name] = lookup_instance
                arg_type = object

            elif isinstance(arg, IdArg):
                arg_type = str

            elif isinstance(arg, EnumArg):
                # Pydantic uses the values of the Enum as the options in the schema.
                # Here we arrange for the keys to be in the schema (what a user supplies)
                # but the values to be what is rendered when jinja refers to the enum
                enum_swapped = {}
                for k, v in arg.values.items():
                    enum_swapped[str(v) if v else str(k)] = k
                # TODO review enums especially with respect to Pydantic 2.7.1
                val_enum = EnumVal(arg.name, enum_swapped)  # type: ignore
                arg_type = val_enum

            else:
                # arg.type is str, int, float, etc.
                arg_type = getattr(builtins, arg.type)
            add_arg(arg.name, arg_type, arg.description, getattr(arg, "default"))

        # add in the calculated values Jinja Templates as Fields in the Entity
        for value in definition.values:
            add_arg(value.name, str, value.description, value.value)

        # add the type literal which discriminates between the different Entity classes
        typ = Literal[full_name]  # type: ignore
        add_arg("type", typ, definition.description, full_name)

        class_name = full_name.replace(".", "_")
        entity_cls = create_model(
            class_name,
            **args,
            __validators__=validators,
            __base__=Entity,
        )  # type: ignore

        # add a link back to the Definition Instance that generated this Entity Class
        entity_cls.__definition__ = definition

        # store this Entity class in the factory
        self._entity_models[full_name] = entity_cls

        return entity_cls

    def _make_entity_models(self, support: Support) -> List[Type[Entity]]:
        """
        Create Entity subclasses for all Definition instances in the given
        Support instance. Returns a list of the Entity subclasses Models.
        """
        entity_names = []
        entity_models = []

        for definition in support.defs:
            if definition.name in entity_names:
                # not tested because schema validation will always catch this first
                raise ValueError(f"Duplicate entity name {definition.name}")

            entity_models.append(self._make_entity_model(definition, support))

            entity_names.append(definition.name)
        return entity_models

    def resolve_sub_entities(self, entities: List[Entity]) -> List[Entity]:
        """
        Recursively resolve SubEntity collections in a list of Entity instances
        """
        resolved_entities: List[Entity] = []
        for parent_entity in entities:
            definition = parent_entity.__definition__
            # add the parent standard entity
            resolved_entities.append(parent_entity)
            # add in SubEntities if any
            for sub_entity in definition.sub_entities:
                # find the Entity Class that the SubEntity represents
                entity_cls = self._entity_models[sub_entity.type]
                # get the SubEntity arguments
                sub_args_dict = sub_entity.model_dump()
                # jinja render any references to parent Args in the SubEntity Args
                for key, arg in sub_args_dict.items():
                    sub_args_dict[key] = UTILS.render(parent_entity, arg)
                # cast the SubEntity to its concrete Entity subclass
                entity = entity_cls(**sub_args_dict)
                # recursively scan the SubEntity for more SubEntities
                resolved_entities.extend(self.resolve_sub_entities([entity]))
        return resolved_entities
