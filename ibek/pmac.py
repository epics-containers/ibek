from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence, Type, TypeVar

from apischema.conversions import Conversion, deserializer, identity
from apischema.deserialization import deserialize
from jinja2 import Template
from typing_extensions import Annotated as A

from ibek.support import desc

T = TypeVar("T")

# /scratch/work/pmac/iocs/lab path on pc0116 for pmac
# /scratch/work/pmac/iocs/lab/labApp/Db/lab_expanded.substitutions contains all substitutions


@dataclass
class DatabaseEntry:
    """ Wrapper for database entries. """

    file: str
    define_args: str


@dataclass
class EntityInstance:
    name: A[str, desc("Name of the entity instance we are creating"), identity]
    script: Sequence[A[str, desc("scripts required for boot script")]] = ()

    # https://wyfo.github.io/apischema/examples/subclasses_union/
    def __init_subclass__(cls):
        # Deserializers stack directly as a Union
        deserializer(Conversion(identity, source=cls, target=EntityInstance))

    def create_scripts(self) -> list:
        return_list = []
        for script in self.script:
            return_list += [Template(script).render(self.__dict__)]
        return return_list

    def create_database(self, databases):
        return_list = []
        print(databases)
        for database in databases:
            file = database.__dict__["file"]
            define_args = database.__dict__["define_args"]
            template = f"dbLoadRecords({file}, {define_args})"
            return_list += [Template(template)]
            print(return_list)
        return return_list


@dataclass
class PmacAsynIPPort(EntityInstance):
    """ defines a connection to a geobrick or pmac over TCP """

    type: Literal["pmac.PmacAsynIPPort"] = "pmac.PmacAsynIPPort"
    IP: A[str, desc("IP address of the pmac to be connected to")] = "127.0.0.0"
    script: Sequence[A[str, desc("scripts required for boot script")]] = (
        'pmacAsynIPConfigure({{name}}, {{IP + "" if ":" in IP else IP + ":1025"}})',
    )


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
    script: Sequence[A[str, desc("scripts required for the boot script")]] = (
        "pmacCreateController({{name}}, {{port}}, 0, 8, {{movingPoll}}, {{idlePoll}})",
        "pmacCreateAxes({{name}}, 8)",
    )

    def create_database(
        self,
        databases=[
            DatabaseEntry(file="pmacController.template", define_args="PMAC = {{ P }}"),
            DatabaseEntry(file="pmacStatus.template", define_args="PMAC = {{ P }}"),
        ],
    ):
        return super().create_database(databases=databases)


@dataclass
class DlsPmacAsynMotor(EntityInstance):
    """ defines an individual axis connected to a geobrick or pmac """

    type: Literal["pmac.DlsPmacAsynMotor"] = "pmac.DlsPmacAsynMotor"
    # port should match a Geobrick or Pmac name
    pmac: A[str, desc("pmac controller for this axis")] = ""
    P: A[str, desc("PV Name for the motor record")] = ""
    axis: A[int, desc("Axis number for this motor")] = 0

    def create_database(
        self,
        databases=[
            DatabaseEntry(
                file="pmac_asyn_Motor.template", define_args="PMAC={{ pmac.P }}"
            )
        ],
    ):
        return super().create_database(databases=databases)


@dataclass
class PmacIOC:
    # instances should possibly exist in base class later
    ioc_name: A[str, desc("Name of the IOC")]
    instances: A[Sequence[EntityInstance], desc("List of entity instances of the IOCs")]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)
