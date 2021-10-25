"""
Functions for generating an IocInstance derived class from a
support module definition YAML file
"""
from __future__ import annotations

import types
from dataclasses import Field, dataclass, field, make_dataclass
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Mapping,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)

from apischema import Undefined, cache, deserialize, deserializer
from apischema.conversions import (
    Conversion,
    LazyConversion,
    identity,
    reset_deserializers,
)
from apischema.metadata import conversion
from typing_extensions import Annotated as A
from typing_extensions import Literal

from . import modules
from .globals import T, desc
from .support import Definition, ObjectArg, StrArg, Support


@dataclass
class Entity:
    """
    A baseclass for all generated Entity classes. Provides the
    deserialize entry point.
    """

    # a link back to the Definition Object that generated this Definition
    __definition__: ClassVar[Definition]
    __instances__: ClassVar[Dict[str, Entity]]

    def __post_init__(self):
        # If there is an argument which is an id then allow deserialization by that
        args = self.__definition__.args
        ids = set(a.name for a in args if isinstance(a, StrArg) and a.is_id)
        assert len(ids) <= 1, f"Multiple id args {list(ids)} defined in {args}"
        if ids:
            # A string id, use that
            inst_id = getattr(self, ids.pop())
        else:
            # No string id, make one
            inst_id = str(len(self.__instances__))
        assert inst_id not in self.__instances__, f"Already got an instance {inst_id}"
        self.__instances__[inst_id] = self


def make_entity_class(definition: Definition, support: Support) -> Type[Entity]:
    """
    We can get a set of Definitions by deserializing an ibek
    support module definition YAML file.

    This function then creates an Entity derived class from each Definition.

    See :ref:`entities`
    """
    fields: List[Union[Tuple[str, type], Tuple[str, type, Field[Any]]]] = []

    # add in each of the arguments
    for arg in definition.args:
        # make_dataclass can cope with string types, so cast them here rather
        # than lookup
        arg_type = cast(type, arg.type)
        metadata: Any = None
        if isinstance(arg, ObjectArg):

            def make_conversion(name: str = arg.type) -> Conversion:
                module_name, entity_name = name.split(".", maxsplit=1)
                entity_cls = getattr(getattr(modules, module_name), entity_name)
                return Conversion(
                    lambda id: entity_cls.__instances__[id], str, entity_cls
                )

            metadata = conversion(deserialization=LazyConversion(make_conversion))
        if arg.description:
            arg_type = A[arg_type, desc(arg.description)]
        if arg.default is Undefined:
            fld = field(metadata=metadata)
        else:
            fld = field(metadata=metadata, default=arg.default)
        fields.append((arg.name, arg_type, fld))

    # put the literal name in as 'type' for this Entity this gives us
    # a unique key for each of the entity types we may instantiate
    full_name = f"{support.module}.{definition.name}"
    fields.append(("type", Literal[full_name], field(default=cast(Any, full_name))))

    namespace = dict(
        __definition__=definition, __instances__={}, __module__="ibek.modules"
    )

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
    for definition in support.definitions:
        entity_cls = make_entity_class(definition, support)
        setattr(module, definition.name, entity_cls)
    return module


def clear_entity_classes():
    """Reset the modules namespaces, deserializers and caches of defined Entity
    subclasses"""
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
