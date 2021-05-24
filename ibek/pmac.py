from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence, Type, TypeVar

from apischema.conversions import Conversion, deserializer, identity
from apischema.deserialization import deserialize
from typing_extensions import Annotated as A

from ibek.support import desc

T = TypeVar("T")


@dataclass
class EntityInstance:
    name: A[str, desc("Name of the entity instance we are creating"), identity]
    script: A[str, desc("boot script jinja template")] = ""

    # https://wyfo.github.io/apischema/examples/subclasses_union/
    def __init_subclass__(cls):
        # Deserializers stack directly as a Union
        deserializer(Conversion(identity, source=cls, target=EntityInstance))


@dataclass
class PmacAsynIPPort(EntityInstance):
    """ defines a connection to a geobrick or pmac over TCP """

    type: Literal["pmac.PmacAsynIPPort"] = "pmac.PmacAsynIPPort"
    IP: A[str, desc("IP address of the pmac to be connected to")] = "127.0.0.0"
    script: A[
        str, desc("jinja template script for ioc.boot")
    ] = "pmacAsynIPConfigure({{name}}, {{IP}})"


@dataclass
class Geobrick(EntityInstance):
    """ defines a Geobrick motion controller """

    type: Literal["pmac.Geobrick"] = "pmac.Geobrick"
    # port should match a PmacAsynIPPort name
    # (we dont have a way for schema to verify this at present -
    # TODO I've looked at this with Tom and it may not be possible)
    port: A[str, desc("Asyn port name for PmacAsynIPPort to connect to")] = ""
    P: A[str, desc("PV Prefix for all pmac db templates")] = ""
    idlePoll: A[int, desc("Idle Poll Period in ms")] = 100
    movingPoll: A[int, desc("Moving Poll Period in ms")] = 500


@dataclass
class DlsPmacAsynMotor(EntityInstance):
    """ defines an individual axis connected to a geobrick or pmac """

    type: Literal["pmac.DlsPmacAsynMotor"] = "pmac.DlsPmacAsynMotor"
    # port should match a Geobrick or Pmac name
    pmac: A[str, desc("pmac controlelr for this axis")] = ""
    P: A[str, desc("PV Name for the motor record")] = ""
    axis: A[int, desc("Axis number for this motor")] = 0


@dataclass
class PmacIOC:
    # instances should possibly exist in base class later
    ioc_name: A[str, desc("Name of the IOC")]
    instances: A[Sequence[EntityInstance], desc("List of entity instances of the IOCs")]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)

