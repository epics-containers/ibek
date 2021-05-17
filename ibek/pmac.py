from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence, Type, TypeVar

from apischema.conversions import Conversion, deserializer, identity
from apischema.deserialization import deserialize
from typing_extensions import Annotated as A

from ibek.support import desc

T = TypeVar("T")


@dataclass
class EntityInstance:
    name: A[str, desc("Name of the entity instance we are creating")]

    # https://wyfo.github.io/apischema/examples/subclasses_union/
    def __init_subclass__(cls):
        # Deserializers stack directly as a Union
        deserializer(Conversion(identity, source=cls, target=EntityInstance))


@dataclass
class PmacAsynIPPort(EntityInstance):
    """ defines a connection to a geobrick or pmac over TCP """

    type: Literal["pmac.PmacAsynIPPort"] = "pmac.PmacAsynIPPort"
    IP: A[str, desc("IP address of the pmac to be connected to")] = "127.0.0.0"


@dataclass
class Geobrick(EntityInstance):
    """ defines a Geobrick motion controller """

    type: Literal["Geobrick"] = "Geobrick"
    port: A[
        PmacAsynIPPort, desc("Asyn port name for PmacAsynIPPort to connect to")
    ] = PmacAsynIPPort("None")
    P: A[str, desc("PV Prefix for all pmac db templates")] = ""
    idlePoll: A[int, desc("Idle Poll Period in ms")] = 100
    movingPoll: A[int, desc("Moving Poll Period in ms")] = 500


@dataclass
class Motor(EntityInstance):
    """ defines an individual axis connected to a geobrick or pmac """

    type: Literal["Motor"] = "Motor"
    port: A[
        PmacAsynIPPort, desc("Asyn port name for PmacAsynIPPort to connect to")
    ] = PmacAsynIPPort("None")
    P: A[str, desc("PV Prefix for all pmac db templates")] = ""
    idlePoll: A[int, desc("Idle Poll Period in ms")] = 100
    movingPoll: A[int, desc("Moving Poll Period in ms")] = 500


@dataclass
class PmacIOC:
    # instances should possibly exist in base class later
    instances: A[Sequence[EntityInstance], desc("List of entity instances of the IOCs")]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)
