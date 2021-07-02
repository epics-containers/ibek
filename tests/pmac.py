from dataclasses import dataclass
from typing import Any, List, Literal, Mapping, Sequence, Type, TypeVar

from apischema.conversions import Conversion, deserializer, identity
from apischema.deserialization import deserialize
from jinja2 import Template
from typing_extensions import Annotated as A

from ibek.support import desc

T = TypeVar("T")


@dataclass
class DatabaseEntry:
    """ Wrapper for database entries. """

    file: str
    define_args: str


@dataclass
class EntityInstance:
    name: A[str, desc("name of instance we are creating"), identity] = ""
    type: A[str, desc("type of the entity instance we are creating")] = ""
    script: Sequence[A[str, desc("scripts required for boot script")]] = ()

    # https://wyfo.github.io/apischema/examples/subclasses_union/
    def __init_subclass__(cls):
        # Deserializers stack directly as a Union
        deserializer(Conversion(identity, source=cls, target=EntityInstance))

    def create_scripts(self) -> List[str]:
        """returns a list of jinja templates representing startup script elements
        for a particular EntityInstance instance. To be expanded using EntityInstance attributes"""
        return_list = []
        for script in self.script:
            return_list += [script]
        return return_list

    def create_database(self, databases: list) -> List[str]:
        """returns a list of jinja templates representing startup dbLoadRecords lines
        for a particular EntityInstance instance. To be expanded using EntityInstance attributes"""
        return_list = []
        for database in databases:
            return_list += [
                f"dbLoadRecords(\"{database.__dict__['file']}\", \"{database.__dict__['define_args']}\")"
            ]
        return return_list


@dataclass
class PmacAsynIPPort(EntityInstance):
    """ defines a connection to a geobrick or pmac over TCP """

    type: A[str, desc("pmac type identifier")] = "pmac.PmacAsynIPPort"
    IP: A[str, desc("IP address of the pmac to be connected to")] = "127.0.0.0"
    script: Sequence[A[str, desc("scripts required for boot script")]] = (
        'pmacAsynIPConfigure({{name}}, {{IP + "" if ":" in IP else IP + ":1025"}})',
    )

    def create_database(self):
        return super().create_database(databases=[])


@dataclass
class PmacIOC:
    # instances should possibly exist in base class later
    ioc_name: A[str, desc("Name of IOC")]
    instances: A[Sequence[EntityInstance], desc("List of entity instances of the IOCs")]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)


@dataclass
class PmacIOC_two:
    # instances should possibly exist in base class later
    ioc_name: A[str, desc("Name of IOC")]
    instances: A[Sequence[EntityInstance], desc("List of entity instances of the IOCs")]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)
