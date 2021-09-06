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
    A base class for all generated Generic IOC classes.

    Each class derived from this dataclass represents a Generic IOC and the
    set of types of Entity it can instantiate. However, note that we
    hold the Entity types in globals::namespace, see NOTE.

    These classes are generated from the support module definition
    YAML files in a generic IOC container.

    Each instance of this class represents an IOC instance with its list
    of instantiated Entities.

    NOTE: because I have made the namespace for generated classes global
    all GenericIoc are exactly the same - just a list of Entity. This
    incorrectly implies that instantiating two Generic IOCs in the same
    session would mean they share all their Entity types.

    I'm not sure this matters, when deserializing any <support>.ibek.yaml
    you get exactly the same class but as a side effect populate the
    global namespace with the Entity Types that the file describes. This
    side effect occurs in the function generator::get_module.

    We don't need to look at two IOCs in the same session, ironically we
    do need to look at multiple Support modules in a session and this
    means that we don't need to distinguish between a support module and
    a set of support modules in an ioc.
    """

    ioc_name: A[str, desc("Name of IOC")]
    description: A[str, desc("Description of what the IOC does")]
    entities: A[Sequence[Entity], desc("List of classes of Entity this IOC supports")]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)
