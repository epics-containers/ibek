from dataclasses import dataclass
from typing import Any, List, Mapping, Sequence, Type, TypeVar

from apischema.deserialization import deserialize
from ruamel.yaml import YAML
from typing_extensions import Annotated as A

from ibek.support import desc

T = TypeVar("T")


@dataclass
class EntityInstance:
    type: A[str, desc("name of type of instance")]
    name: A[str, desc("Name of the entity instance we are creating")]
    IP: A[str, desc("IP address of the pmac to be connected to")]


@dataclass
class PmacAsynIPPort:
    IP: A[str, desc("IP address of the pmac to be connected to")]


@dataclass
class PmacIOC:
    # instances should possibly exist in base class later
    instances: A[Sequence[EntityInstance], desc("List of entity instances of the IOCs")]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)
