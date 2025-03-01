"""
A class for constructing Entity classes from EntityModels
"""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, create_model
from pydantic_core import PydanticUndefined
from ruamel.yaml.main import YAML

from ibek.globals import JINJA
from ibek.ibek_builtin.repeat import REPEAT_TYPE, RepeatEntity

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
        self._entity_types: dict[str, EntityModel] = {}
        # starting a new EntityFactory implies we should throw away any existing
        # Entity instances - this is required for tests which create multiple
        # EntityFactories
        clear_entity_model_ids()

    def make_entity_types(self, entity_model_yaml: list[Path]) -> list[EntityModel]:
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
            self._entity_types[REPEAT_TYPE] = RepeatEntity  # type: ignore
        except Exception:
            print(f"VALIDATION ERROR READING {entity_model}")
            raise

        return list(self._entity_types.values())

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
        self._entity_types[full_name] = entity_cls

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
        self, repeat_entity: RepeatEntity, parent_entity: Entity
    ) -> list[Entity]:
        """
        Resolve a repeat Entity into a list of Entity instances
        """
        resolved_entities: list[Entity] = []

        # ensure correct class - it will be a generic Entity in subentities
        repeat_entity = RepeatEntity(**repeat_entity.model_dump())
        # also ensure repeat fields are rendered (in subentities they are not)
        repeat_entity.values = UTILS.render(parent_entity, repeat_entity.values, "list")
        repeat_entity.variable = UTILS.render(parent_entity, repeat_entity.variable)

        for value in repeat_entity.values:
            new_entity_cls = self._entity_types[repeat_entity.entity["type"]]
            new_params: dict[str, Any] = {}
            for key, param in repeat_entity.entity.items():
                if key == "entity" and new_params.get("type") == REPEAT_TYPE:
                    # defer rendering of the inner entity in nested repeats
                    new_params[key] = param
                else:
                    # insert the iterator variable into the context
                    context = repeat_entity.model_dump()
                    if parent_entity:
                        context.update(parent_entity.model_dump())
                    context[repeat_entity.variable] = value
                    # jinja render the parameter in the repeat entity
                    new_params[key] = UTILS.render(context, param)

            # create the new repeated entity from its type and parameters
            new_entity = new_entity_cls(**new_params)  # type: ignore
            assert isinstance(new_entity, Entity)

            resolved_entities.extend(self.resolve_sub_entities([new_entity]))

        return resolved_entities

    def resolve_sub_entities(self, entities: list[Entity]) -> list[Entity]:
        """
        Recursively resolve SubEntity collections in a list of Entity instances
        """
        resolved_entities: list[Entity] = []
        for parent_entity in entities:
            if parent_entity.type == REPEAT_TYPE:
                # resolve repeats in the parent entity
                resolved_entities.extend(self._resolve_repeat(parent_entity, {}))  # type: ignore
            else:
                # add the current parent entity
                resolved_entities.append(parent_entity)
                # add in SubEntities if any
                for sub_entity in parent_entity._model.sub_entities:
                    if sub_entity.type == REPEAT_TYPE:
                        # if the sub entity is a repeat resolve repeats
                        # passing parent in, so it's arguments can be merged into context
                        resolved_entities.extend(
                            self._resolve_repeat(sub_entity, parent_entity)  # type: ignore
                        )
                    else:
                        # find the Entity Class that the SubEntity represents
                        entity_cls = self._entity_types[sub_entity.type]
                        # get the SubEntity arguments
                        sub_params_dict = sub_entity.model_dump()
                        # jinja render any references to parent Params in the SubEntity Args
                        for key, param in sub_params_dict.items():
                            sub_params_dict[key] = UTILS.render(parent_entity, param)
                        # cast the SubEntity to its concrete Entity subclass
                        new_entity = entity_cls(**sub_params_dict)  # type: ignore
                        # recursively scan the SubEntity for more SubEntities
                        resolved_entities.extend(
                            self.resolve_sub_entities([new_entity])
                        )

        return resolved_entities
