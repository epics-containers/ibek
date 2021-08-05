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
class Entity:
    """
    A single entity that an IOC can instantiate
    """

    name: A[str, desc("Publish Entity as type <module>.<name> for IOC instances")]
    args: A[Sequence[Arg], desc("The arguments IOC instance should supply")] = ()
    databases: A[Sequence[Database], desc("Databases to instantiate")] = ()
    script: A[
        Sequence[str], desc("Startup script snippet defined as Jinja template")
    ] = ()


@dataclass
class EntityInstance:
    """
    A baseclass for all generated EntityInstance classes. Provides the
    deserialize entry point.
    """

    # a link back to the Entity Object that generated this EntityInstance
    entity: ClassVar[Entity]

    def __init_subclass__(cls) -> None:
        deserializer(Conversion(identity, source=cls, target=EntityInstance))


@dataclass
class IocInstance:
    """
    A base class for all generated module classes. Provides the deserialize
    entry point.
    """

    ioc_name: str
    instances: Sequence[EntityInstance]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)


@dataclass
class Support:
    """Lists the entities a support module can build"""

    module: A[str, desc("Support module name, normally the repo name")]
    entities: A[
        Sequence[Entity], desc("The entities an IOC can create using this module")
    ]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)
