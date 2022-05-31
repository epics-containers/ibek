"""
Functions for generating an IocInstance derived class from a
support module definition YAML file
"""
from __future__ import annotations

import builtins
import types
from dataclasses import Field, dataclass, field, make_dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple, Type, cast

from apischema import (
    Undefined,
    ValidationError,
    cache,
    deserialize,
    deserializer,
    identity,
    schema,
)
from apischema.conversions import Conversion, reset_deserializers
from apischema.metadata import conversion
from typing_extensions import Annotated as A
from typing_extensions import Literal

from . import modules
from .globals import T, desc
from .support import Definition, IdArg, ObjectArg, Support


class Entity:
    """
    A baseclass for all generated Entity classes. Provides the
    deserialize entry point.
    """

    # a link back to the Definition Object that generated this Definition
    __definition__: Definition

    entity_enabled: bool

    def __post_init__(self):
        # If there is an argument which is an id then allow deserialization by that
        args = self.__definition__.args
        ids = set(a.name for a in args if isinstance(a, IdArg))
        assert len(ids) <= 1, f"Multiple id args {list(ids)} defined in {args}"
        if ids:
            # A string id, use that
            inst_id = getattr(self, ids.pop())
            assert inst_id not in id_to_entity, f"Already got an instance {inst_id}"
            id_to_entity[inst_id] = self


id_to_entity: Dict[str, Entity] = {}


def make_entity_class(definition: Definition, support: Support) -> Type[Entity]:
    """
    We can get a set of Definitions by deserializing an ibek
    support module definition YAML file.

    This function then creates an Entity derived class from each Definition.

    See :ref:`entities`
    """
    fields: List[Tuple[str, type, Field[Any]]] = []

    # add in each of the arguments
    for arg in definition.args:
        # make_dataclass can cope with string types, so cast them here rather
        # than lookup
        metadata: Any = None
        arg_type: Type
        if isinstance(arg, ObjectArg):

            def lookup_instance(id):
                try:
                    return id_to_entity[id]
                except KeyError:
                    raise ValidationError(f"{id} is not in {list(id_to_entity)}")

            metadata = conversion(
                deserialization=Conversion(lookup_instance, str, Entity)
            ) | schema(extra={"vscode_ibek_plugin_type": "type_object"})
            arg_type = Entity
        elif isinstance(arg, IdArg):
            arg_type = str
            metadata = schema(extra={"vscode_ibek_plugin_type": "type_id"})
        else:
            # arg.type is str, int, float, etc.
            arg_type = getattr(builtins, arg.type)
        if arg.description:
            arg_type = A[arg_type, desc(arg.description)]  # type: ignore
        if arg.default is Undefined:
            fld = field(metadata=metadata)
        else:
            fld = field(metadata=metadata, default=arg.default)
        fields.append((arg.name, arg_type, fld))  # type: ignore

    # put the literal name in as 'type' for this Entity this gives us
    # a unique key for each of the entity types we may instantiate
    full_name = f"{support.module}.{definition.name}"
    fields.append(
        (
            "type",
            Literal[full_name],  # type: ignore
            field(default=cast(Any, full_name)),
        )
    )

    # add a field so we can control rendering of the entity without having to delete
    # it
    fields.append(("entity_enabled", bool, field(default=cast(Any, True))))

    namespace = dict(__definition__=definition)

    # make the Entity derived dataclass for this EntityClass, with a reference
    # to the Definition that created it
    entity_cls = make_dataclass(full_name, fields, bases=(Entity,), namespace=namespace)
    deserializer(Conversion(identity, source=entity_cls, target=Entity))
    return entity_cls


def make_entity_classes(support: Support) -> types.SimpleNamespace:
    """Create `Entity` subclasses for all `Definition` objects in the given
    `Support` instance, put them in a namespace in `ibek.modules` and return
    it"""
    module = types.SimpleNamespace()
    assert not hasattr(
        modules, support.module
    ), f"Entity classes already created for {support.module}"
    setattr(modules, support.module, module)
    modules.__all__.append(support.module)
    for definition in support.defs:
        entity_cls = make_entity_class(definition, support)
        setattr(module, definition.name, entity_cls)
    return module


def clear_entity_classes():
    """Reset the modules namespaces, deserializers and caches of defined Entity
    subclasses"""
    id_to_entity.clear()
    while modules.__all__:
        delattr(modules, modules.__all__.pop())
    reset_deserializers(Entity)
    cache.reset()


@dataclass
class IOC:
    """
    Used to load an IOC instance entities yaml file into memory using
    IOC.deserialize(YAML().load(ioc_instance_yaml)).

    Before loading the entities file all Entity classes that it contains
    must be defined in modules.py. This is achieved by deserializing all
    support module definitions yaml files used by this IOC and calling
    make_entity_classes(support_module).
    """

    ioc_name: A[str, desc("Name of IOC instance")]
    description: A[str, desc("Description of what the IOC does")]
    entities: A[Sequence[Entity], desc("List of entities this IOC instantiates")]
    generic_ioc_image: A[str, desc("The generic IOC container image registry URL")]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)
