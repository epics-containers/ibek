"""
A class for constructing Entity classes from EntityModels
"""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal, Tuple, Type

from pydantic import Field, create_model
from pydantic_core import PydanticUndefined
from ruamel.yaml.main import YAML

from ibek.globals import JINJA

from .ioc import Entity, EnumVal, clear_entity_model_ids
from .parameters import EnumParam, IdParam, ObjectParam
from .support import EntityModel, Support
from .utils import UTILS


class EntityFactory:
    def __init__(self) -> None:
        """
        A class to create `Entity` models from `EntityModel`s.

        Created models are stored in `self._entity_models` to lookup when
        resolving nested `SubEntity`s.
        """
        self._entity_models: Dict[str, Type[Entity]] = {}
        # starting a new EntityFactory implies we should throw away any existing
        # Entity instances - this is required for tests which create multiple
        # EntityFactories
        clear_entity_model_ids()

    def make_entity_models(self, entity_model_yaml: List[Path]) -> List[Type[Entity]]:
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
                self._make_entity_models(support)
        except Exception:
            print(f"VALIDATION ERROR READING {entity_model}")
            raise

        return list(self._entity_models.values())

    def _make_entity_model(self, model: EntityModel, support: Support) -> Type[Entity]:
        """
        Create an Entity Model from a EntityModel instance and a Support instance.
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

        args: Dict[str, Tuple[type, Any]] = {}
        validators: Dict[str, Any] = {}

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
            add_arg(name, type, param.description, getattr(param, "default"))  # type: ignore

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

    def _make_entity_models(self, support: Support) -> List[Type[Entity]]:
        """
        Create Entity subclasses for all EntityModel instances in the given
        Support instance. Returns a list of the Entity subclasses Models.
        """
        entity_names = []
        entity_models = []

        for model in support.entity_models:
            if model.name in entity_names:
                # not tested because schema validation will always catch this first
                raise ValueError(f"Duplicate entity name {model.name}")

            entity_models.append(self._make_entity_model(model, support))

            entity_names.append(model.name)
        return entity_models

    def resolve_sub_entities(self, entities: List[Entity]) -> List[Entity]:
        """
        Recursively resolve SubEntity collections in a list of Entity instances
        """
        resolved_entities: List[Entity] = []
        for parent_entity in entities:
            model = parent_entity._model
            # add the parent standard entity
            resolved_entities.append(parent_entity)
            # add in SubEntities if any
            for sub_entity in model.sub_entities:
                # find the Entity Class that the SubEntity represents
                entity_cls = self._entity_models[sub_entity.type]
                # get the SubEntity arguments
                sub_params_dict = sub_entity.model_dump()
                # jinja render any references to parent Params in the SubEntity Args
                for key, param in sub_params_dict.items():
                    sub_params_dict[key] = UTILS.render(parent_entity, param)
                # cast the SubEntity to its concrete Entity subclass
                entity = entity_cls(**sub_params_dict)
                # recursively scan the SubEntity for more SubEntities
                resolved_entities.extend(self.resolve_sub_entities([entity]))
        return resolved_entities
