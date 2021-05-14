from dataclasses import dataclass
from typing import Any, List, Mapping, Type, TypeVar

from apischema.deserialization import deserialize
from typing_extensions import Annotated as A

from ibek.support import desc

T = TypeVar("T")


@dataclass
class EntityInstance:
    name: A[str, desc("Name of the entity instance we are creating")]


@dataclass
class PmacAsynIPPort:
    IP: A[str, desc("IP address of the pmac to be connected to")]


@dataclass
class PmacIOC:
    # instances should possibly exist in base class later
    instances: A[List[EntityInstance], desc("List of entity instances of the IOCs")]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)
