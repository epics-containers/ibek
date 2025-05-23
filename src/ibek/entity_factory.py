"""
A class for constructing Entity classes from EntityModels
"""

from __future__ import annotations

import builtins
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, create_model
from pydantic_core import PydanticUndefined
from ruamel.yaml.main import YAML

from ibek.globals import JINJA
from ibek.ibek_builtin.repeat import REPEAT_TYPE, RepeatEntity
from ibek.sub_entity import SubEntity

from .ioc import Entity, EnumVal, clear_entity_model_ids
from .parameters import EnumParam, IdParam, ObjectParam
from .support import EntityModel, Support
from .utils import UTILS


class EntityFactory:
    def __init__(self) -> None:
        """
        A class to create `Entity` types from `EntityModel` instances.

        To understand this class be aware that these are equivalent:-
          EntityModel instance == Entity class.
        i.e. when we instantiate an EntityModel we are creating a new
        dynamic Entity class.

        EntityModel instantiation happens when:-

        1. Deserializing a support module yaml file
        2. calling make_entity_model() in ibek_builtin.repeat.py

        Instantiating an Entity itself is the step that happens when
        deserializing a ioc.yaml. Entities in turn know how to make database
        and startup script entries for IOC instance.

        I have replaced all references in the code to type[Entity] with
        EntityModel for consistency.

        Created models are stored in `self._entity_models` to lookup when
        resolving nested `SubEntity`s.
        """
        self._entity_models: dict[str, EntityModel] = {}
        # starting a new EntityFactory implies we should throw away any existing
        # Entity instances - this is required for tests which create multiple
        # EntityFactories
        clear_entity_model_ids()

    def make_entity_models(self, entity_model_yaml: list[Path]) -> list[EntityModel]:
        """
        Read a set of *.ibek.support.yaml files and generate Entity classes
        from their EntityModel entries
        """

        try:
            for entity_model in entity_model_yaml:
                support_dict = YAML(typ="safe").load(entity_model)

                Support.model_validate(support_dict)

                # deserialize the support module yaml file
                support = Support(**support_dict)
                # make Entity classes described in the support module yaml file
                self._make_entity_types(support)

            # also add builtin entity types "ibek.*"
            self._entity_models[REPEAT_TYPE] = RepeatEntity  # type: ignore
        except Exception:
            print(f"VALIDATION ERROR READING {entity_model}")
            raise

        return list(self._entity_models.values())

    def _make_entity_type(self, model: EntityModel, support: Support) -> EntityModel:
        """
        Create an Entity type from a EntityModel instance and it's containing
        Support instance.
        """

        def add_arg(name, typ, description, default):
            if default is None:
                default = PydanticUndefined
            # cheesy check for enum, can this be improved?
            if typ in [str, object] or "enum" in str(typ):
                args[name] = (Annotated[typ, Field(description=description)], default)
            else:
                args[name] = (
                    Annotated[
                        Annotated[
                            str,
                            Field(
                                description=f"jinja that renders to {typ}",
                                pattern=JINJA,
                            ),
                        ]
                        | Annotated[typ, Field(description=description)],
                        Field(
                            description=f"union of {typ} and jinja "
                            "representation of {typ}"
                        ),
                    ],
                    default,
                )

        args: dict[str, tuple[type, Any]] = {}
        validators: dict[str, Any] = {}

        # fully qualified name of the Entity class including support module
        full_name = f"{support.module}.{model.name}"

        # add in each of the parameters as a Field in the Entity
        for name, param in model.parameters.items():
            type: Any

            if isinstance(param, ObjectParam):
                # we now defer the lookup of the object until whole model validation
                type = object

            elif isinstance(param, IdParam):
                type = str

            elif isinstance(param, EnumParam):
                # Pydantic uses the values of the Enum as the options in the schema.
                # Here we arrange for the keys to be in the schema (what a user supplies)
                # but the values to be what is rendered when jinja refers to the enum
                enum_swapped = {}
                for k, v in param.values.items():
                    enum_swapped[str(v) if v else str(k)] = k
                # TODO review enums especially with respect to Pydantic 2.7.1
                val_enum = EnumVal(name, enum_swapped)  # type: ignore
                type = val_enum

            else:
                # arg.type is str, int, float, etc.
                type = getattr(builtins, param.type)
            add_arg(name, type, param.description, param.default)  # type: ignore

        # add the type literal which discriminates between the different Entity classes
        typ = Literal[full_name]  # type: ignore
        args["type"] = (typ, Field(description=model.description))

        class_name = full_name.replace(".", "_")
        entity_cls = create_model(
            class_name,
            **args,
            __validators__=validators,
            __base__=Entity,
        )  # type: ignore

        # add a link back to the EntityModel Instance that generated this Entity Class
        entity_cls._model = model

        # store this Entity class in the factory
        self._entity_models[full_name] = entity_cls

        return entity_cls

    def _make_entity_types(self, support: Support) -> list[EntityModel]:
        """
        Create Entity subclasses for all EntityModel instances in the given
        Support instance. Returns a list of the Entity subclasses Models.
        """
        entity_names = []
        entity_types = []

        for model in support.entity_models:
            if model.name in entity_names:
                # not tested because schema validation will always catch this first
                raise ValueError(f"Duplicate entity name {model.name}")

            entity_types.append(self._make_entity_type(model, support))

            entity_names.append(model.name)
        return entity_types

    def _resolve_repeat(
        self, repeat_entity: RepeatEntity, context: dict[str, Any]
    ) -> list[Entity]:
        """
        Resolve a repeat Entity into a list of Entity instances
        """
        resolved_entities: list[Entity] = []

        for index, value in enumerate(repeat_entity.values):
            context[repeat_entity.variable] = value
            context[f"{repeat_entity.variable}_num"] = index

            # create the new repeated entity using a dict of arguments
            new_entity = repeat_entity.entity.copy()
            resolved_entities.extend(
                self.resolve_sub_entities([new_entity], context.copy())
            )

        return resolved_entities

    def _make_entity(self, params: dict[str, Any], context: dict[str, Any]) -> Entity:
        # jinja render the parent entity parameters
        for key, param in params.items():
            params[key] = UTILS.render(context, param)

        # create the correct class with new params
        parent_cls = self._entity_models[params["type"]]
        return parent_cls(**params)  # type: ignore

    def resolve_sub_entities(
        self, entities: Sequence[dict | Entity | SubEntity], context: dict[str, Any]
    ) -> list[Entity]:
        """
        Recursively resolve SubEntity collections and Repeat Entities
        in a list of Entity instances

        entities:   list of Entity instances to resolve. These will be Entity
                    subclasses in the root call, but will be dicts in recursive
                    calls via subentities or repeats.
        context:    dictionary of variables to pass to jinja when rendering,
                    this list accumulates as we recurse subentities/repeats
        """
        resolved_entities: list[Entity] = []

        # copy the context for the recursive branches
        context = context.copy()

        for parent_entity in entities:
            if isinstance(parent_entity, dict):
                # convert dictionary to specific Entity with jinja rendering
                parent_entity = self._make_entity(parent_entity, context)

            elif isinstance(parent_entity, SubEntity) or isinstance(
                parent_entity, RepeatEntity
            ):
                # jinja render the arguments of the SubEntity/RepeatEntity
                parent_entity = self._make_entity(parent_entity.model_dump(), context)

            # this parent entity's parameters are passed to children via context
            context.update(parent_entity.model_dump())

            if isinstance(parent_entity, RepeatEntity):
                # resolve repeats in this parent entity
                resolved_entities.extend(self._resolve_repeat(parent_entity, context))
            else:
                # add the current parent entity to the resolved list
                resolved_entities.append(parent_entity)
                # add in SubEntities if any
                for sub_entity in parent_entity._model.sub_entities:
                    # recursively scan the SubEntity for more SubEntities
                    resolved_entities.extend(
                        self.resolve_sub_entities([sub_entity], context)
                    )

        return resolved_entities
