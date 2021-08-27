"""
The Support Class represents a deserialized <MODULE_NAME>.ibek.yaml file.
It contains a hierarchy of Entity dataclasses.
"""

from dataclasses import dataclass
from typing import Any, ClassVar, Mapping, Sequence, Type

from apischema import deserialize, deserializer
from apischema.conversions import Conversion, identity
from typing_extensions import Annotated as A

from ibek.argument import Arg
from ibek.globals import T, desc

"""
TODO: There are a couple of problems with deserialize and defaults. These
are worked around as follows. I need to verify that this is the best
approach to dealing with this.

- str default "" == no default
    - using " " for now (I'm not sure I'm happy with this)
- int default 0 or null == no default
    - using "0" and added str type to IntArg
- float values in json have a trailing 'f' and this comes back as str on deserialize
    - added str type to FloatArg
    - added __post_init__ to FloatArg to strip the 'f'
"""


@dataclass
class Database:
    """
    A database file that should be loaded by the startup script and its args
    """

    file: A[str, desc("Filename of the database template in <module_root>/db")]
    include_args: A[
        Sequence[str], desc("List of args to pass through to database")
    ] = ()
    define_args: A[str, desc("Arg string list to be generated as Jinja template")] = ""


@dataclass
class Definition:
    """
    A single definition of a class of Entity that an IOC instance may instantiate
    """

    name: A[str, desc("Publish Definition as type <module>.<name> for IOC instances")]
    args: A[Sequence[Arg], desc("The arguments IOC instance should supply")] = ()
    databases: A[Sequence[Database], desc("Databases to instantiate")] = ()
    script: A[
        Sequence[str], desc("Startup script snippet defined as Jinja template")
    ] = ()


@dataclass
class Entity:
    """
    A baseclass for all generated Entity classes. Provides the
    deserialize entry point.
    """

    # a link back to the Entity Object that generated this Entity
    entity: ClassVar[Definition]

    def __init_subclass__(cls) -> None:
        deserializer(Conversion(identity, source=cls, target=Entity))


@dataclass
class GenericIoc:
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

    ioc_name: str
    description: str
    entities: Sequence[Entity]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)


@dataclass
class Support:
    """
    Lists the definitions for a support module, this defines what Entities it supports

    Provides the deserialize entry point.
    """

    module: A[str, desc("Support module name, normally the repo name")]
    definitions: A[
        Sequence[Definition],
        desc("The definitions an IOC can create using this module"),
    ]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)
