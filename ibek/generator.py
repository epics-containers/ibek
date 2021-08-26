"""
Functions for generating an IocInstance derived class from a
support module definition YAML file
"""

import builtins
from dataclasses import Field, field, make_dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple, Type, Union, cast

from apischema.utils import Undefined
from ruamel.yaml import YAML
from typing_extensions import Annotated as A
from typing_extensions import Literal

from ibek.globals import desc, namespace
from ibek.support import Definition, Entity, IocInstance, Support


def from_support_module_definition(definition_file: Path) -> Type["IocInstance"]:
    """
    Read in a support module definition file and
    generate an IocInstance derived class
    """

    # Deserialize the Support Module Definition yaml file into an
    # instance of the Support class
    yaml = YAML()
    with open(definition_file, "r") as f:
        support = Support.deserialize(yaml.load(f))

    # Create dataclasses from the Support Module Definition
    module_dataclass = get_module(support)
    return module_dataclass


def get_module(support: Support) -> Type[IocInstance]:
    """
    Generate an IocInstance derived class with its a set of Entity classes,

    from a support module definition.

    TODO: this function needs to be able to agreggate multiple Support module
    definition files and hence list the Entity classes from all of the
    Support modules within a given Generic IOC Container
    """

    # place the Entity base class in the dynamic classes global namespace
    namespace["Entity"] = Entity

    for entity in support.definitions:
        get_entity_classes(
            entity, namespace["Entity"], namespace, support.module,
        )

    namespace[support.module] = make_dataclass(
        support.module,
        [
            ("ioc_name", A[str, desc("Name of IOC")]),
            (
                "entities",
                A[Sequence[Entity], desc("List of entity instances of the IOCs")],
            ),
        ],
        bases=(IocInstance,),
    )
    return namespace[support.module]


def get_entity_classes(
    entity: Definition, baseclass: Any, namespace: Dict[str, Any], module_name: str,
):
    """
    We can get a set of Definitions by deserializing an ibek
    support module definition YAML file.

    This function then creates an Entity derived class from each Definition.
    See :ref:`entities`
    """
    # we need to qualify the name with the module so as to avoid cross
    # module name clashes
    name = f"{module_name}.{entity.name}"

    if name in namespace:
        return

    # put the literal name in as 'type' for this Entity this gives us
    # a unique key for each of the entity types we may instantiate
    fields: List[Any] = [(str("type"), Literal[name])]

    # add in each of the arguments

    for arg in entity.args:
        this_field: Union[str, Tuple[str, type], Tuple[str, type, Field[Any]]] = ""

        if arg.description:
            arg_type = getattr(builtins, arg.type)
            this_field = (
                arg.name,
                A[arg_type, desc(arg.description)],
            )
        else:
            this_field = (arg.name, getattr(builtins, arg.type))
        if arg.default is not Undefined:
            default: Field[Any] = field(default=arg.default)
            this_field += (default,)

        fields.append(this_field)

    # make the Entity derived dataclass for this EntityClass
    entity_cls: Entity = cast(Entity, make_dataclass(name, fields, bases=(baseclass,)))

    # add a reference to the entity class for this entity instance class
    # (oh boy, that sounds confusing: see `explanations/entities`)
    setattr(entity_cls, "entity", entity)

    namespace[name] = entity_cls
