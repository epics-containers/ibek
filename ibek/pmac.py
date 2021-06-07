from dataclasses import dataclass
from typing import Any, List, Literal, Mapping, Sequence, Type, TypeVar

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
    type: A[str, desc("type of the entity instance we are creating")] = ""
    name: A[str, desc("Name of the entity instance we are creating"), identity] = ""
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

    type: Literal["pmac.PmacAsynIPPort"] = "pmac.PmacAsynIPPort"
    IP: A[str, desc("IP address of the pmac to be connected to")] = "127.0.0.0"
    script: Sequence[A[str, desc("scripts required for boot script")]] = (
        'pmacAsynIPConfigure({{name}}, {{IP + "" if ":" in IP else IP + ":1025"}})',
    )

    def create_database(self):
        return super().create_database(databases=[])


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

    timeout: A[int, desc("timeout time")] = 200
    feedrate: A[int, desc("feedrate")] = 150
    ControlIP: A[str, desc("dls-pmac-control.py IP or Hostname")] = ""
    ControlPort: A[str, desc("dls-pmac-control.py Port")] = ""
    ControlMode: A[
        str, desc("dls-pmac-control.py Mode (tcp.ip or terminal server")
    ] = ""
    Description: A[str, desc("geobrick description")] = ""

    CSG0: A[str, desc("Name for Coordinate System Group 0")] = ""
    CSG1: A[str, desc("Name for Coordinate System Group 1")] = ""
    CSG2: A[str, desc("Name for Coordinate System Group 2")] = ""
    CSG3: A[str, desc("Name for Coordinate System Group 3")] = ""
    CSG4: A[str, desc("Name for Coordinate System Group 4")] = ""
    CSG5: A[str, desc("Name for Coordinate System Group 5")] = ""
    CSG6: A[str, desc("Name for Coordinate System Group 6")] = ""
    CSG7: A[str, desc("Name for Coordinate System Group 7")] = ""

    def create_database(
        self,
        databases=[
            DatabaseEntry(
                file="pmacController.template",
                define_args=(
                    "PORT={{ port }}, "
                    "P={{ P }}, "
                    "TIMEOUT={{ timeout }}, "
                    "FEEDRATE={{ feedrate}}, "
                    "CSG0={{ CSG0 }}, "
                    "CSG1={{ CSG1 }}, "
                    "CSG2={{ CSG2 }}, "
                    "CSG3={{ CSG3 }}, "
                    "CSG4={{ CSG4 }}, "
                    "CSG5={{ CSG5 }}, "
                    "CSG6={{ CSG6 }}, "
                    "CSG7={{ CSG7 }}, "
                ),
            ),
            DatabaseEntry(
                file="pmacStatus.template",
                # define_args="PORT = {{ port }}, P = {{ P }}, Description = {{ }}, ControlIP = {{ ControlIP }}, ControlPort = {{ ControlPort }}, ControlMode = {{ ControlMode }}",
                define_args=(
                    "PORT = {{ port }}, "
                    "P = {{ P }}, "
                    "Description = {{ Description }}, "
                    "ControlIP = {{ ControlIP }}, "
                    "ControlPort = {{ ControlPort }}, "
                    "ControlMode = {{ ControlMode }}"
                ),
            ),
        ],
    ):
        return super().create_database(databases=databases)


@dataclass
class DlsPmacAsynMotor(EntityInstance):
    """ defines an individual axis connected to a geobrick or pmac """

    type: Literal["pmac.DlsPmacAsynMotor"] = "pmac.DlsPmacAsynMotor"
    # port should match a Geobrick or Pmac name
    P: A[str, desc("Device Prefix")] = ""
    M: A[str, desc("Device Suffix")] = ""
    PORT: A[str, desc("Delta tau motor controller")] = ""
    ADDR: A[int, desc("Address on controller")] = 0
    DESC: A[str, desc("Description, displayed on EDM screen")] = ""
    MRES: A[float, desc("Motor Step Size (EGU)")] = 0.001
    VELO: A[float, desc("Velocity (EGU/s)")] = 20
    PREC: A[float, desc("Display Precission")] = 3
    EGU: A[str, desc("Engineering Units")] = "mm"
    TWV: A[int, desc("Tweak Step Size (EGU")] = 1
    DTYP: A[str, desc("Datatype of record")] = "pmac.DlsPmacAsynMotor"
    DIR: A[int, desc("User direction")] = 0
    VBAS: A[float, desc("Base Velocity (EGU/s)")] = 0
    VMAX: A[float, desc("Max Velocity (EGU/s)")] = 20  # VELO
    ACCL: A[float, desc("Seconds to Velocity")] = 0.5
    BDST: A[float, desc("BL Distance (EGU)")] = 0
    BVEL: A[float, desc("BL Velocity(EGU/s)")] = 0
    BACC: A[str, desc("BL Seconds to Veloc")] = ""
    DHLM: A[float, desc("Dial High Limit")] = 10000
    DLMM: A[float, desc("Dial low limit")] = -10000
    HLM: A[float, desc("User High Limit")] = None
    LLM: A[float, desc("User Low Limit")] = None
    HLSV: A[str, desc("HW Lim, Violation Svr")] = "MAJOR"
    INIT: A[str, desc("Startup commands")] = ""
    SREV: A[float, desc("Steps per Revolution")] = 1000
    RRES: A[float, desc("Readback Step Size (EGU")] = None
    ERES: A[float, desc("Encoder Step Size (EGU)")] = None
    JAR: A[float, desc("Jog Acceleration (EGU/s^2)")] = None
    UEIP: A[int, desc("Use Encoder If Present")] = 0
    URIP: A[int, desc("Use RDBL If Present")] = 0
    RDBL: A[str, desc("Readback Location, set URIP =1 if you specify this")] = ""
    RLNK: A[str, desc("Readback output link")] = ""
    RTRY: A[int, desc("Max retry count")] = 0
    DLY: A[float, desc("Readback settle time (s)")] = 0
    OFF: A[float, desc("User Offset (EGU)")] = 0
    RDBD: A[float, desc("Retry Deadband (EGU)")] = None
    FOFF: A[int, desc("Freeze Offset, 0=variable, 1=frozen")] = 0
    ADEL: A[float, desc("Alarm monitor deadband (EGU)")] = 0
    NTM: A[int, desc("New Target Monitor, only set to 0 for soft motors")] = 1
    FEHEIGH: A[float, desc("HIGH limit for following error")] = 0
    FEHIHI: A[float, desc("HIHI limit for following error")] = 0
    FEHHSV: A[str, desc("HIHI alarm severity for following error")] = "NO_ALARM"
    FEHSV: A[str, desc("HIGH alarm severity for following error")] = "NO_ALARM"
    SCALE: A[int, desc("")] = 1
    HOMEVIS: A[int, desc("If 1 then home is visible on the gui")] = 1
    HOMEVISSTR: A[str, desc("")] = "Use motor summary screen"
    name: A[str, desc("Object name and gui association name")] = ""
    alh: A[
        float,
        desc("Set this to alh to add the motor to the alarm handler and send emails"),
    ] = None
    gda_name: A[str, desc("Name to export this as to GDA")] = ""
    gda_desc: A[str, desc("Description to export as to GDA")] = ""
    SPORT: A[str, desc("Delta tau motor controller comms port")] = ""
    HOME: A[
        str, desc("Prefix for autohome instance. Defaults to $(P) If unspecified")
    ] = ""
    ALLOW_HOMED_SET: A[
        str, desc("Set to a blank to allow this axis to have its homed")
    ] = ""
    axis: A[int, desc("Axis number for this motor")] = 0

    def create_database(
        self,
        databases=[
            DatabaseEntry(
                file="pmac_asyn_Motor.template",
                define_args=(
                    "P={{ P }},"
                    "M = {{ M }},"
                    "PORT={{ PORT }},"
                    "ADDR={{ ADDR }},"
                    "DESC={{ DESC }},"
                    "MRES={{ MRES }},"
                    "VELO={{ VELO }},"
                    "PREC={{ PREV }},"
                    "EGU={{ EGU }},"
                    "TWV={{ TWV }},"
                    "DTYP={{ DTYP }},"
                    "DIR={{ DIR }},"
                    "VBAS={{ VBAS }},"
                    "VMAX={{ VMAX }},"
                    "ACCL={{ ACCL }},"
                    "BDST={{ BDST }},"
                    "BVEL={{ BVEL }},"
                    "BACC={{ BACC }},"
                    "DHLM={{ DHLM }},"
                    "DLLM={{ DLLM }},"
                    "HLM={{ HLM }},"
                    "LLM={{ LLM }},"
                    "HLSV={{ HLSV }},"
                    "INIT={{ INIT }},"
                    "SREV={{ SREV }},"
                    "RRES={{ RRES }},"
                    "ERES={{ ERES }},"
                    "JAR={{ JAR }},"
                    "UEIP={{ UEIP }},"
                    "RDBL={{ RDBL }},"
                    "RLINK={{ RLINK }},"
                    "RTRY={{ RTRY }},"
                    "DLY={{ DLY }},"
                    "OFF={{ OFF }},"
                    "RDBD={{ RDBD }},"
                    "FOFF={{ FOFF }},"
                    "ADEL={{ ADEL }},"
                    "NTM={{ NTM }},"
                    "FEHIGH={{ FEHEIGH }},"
                    "FEHIHI={{ FEHIHI }},"
                    "FEHHSV={{ FEHHSV }},"
                    "FEHSV={{ FEHSV }},"
                    "SCALE={{ SCALE }},"
                    "HOMEVIS={{ HOMEVIS }},"
                    "HOMEVISSTR={{ HOMEVISSTR }},"
                    "name={{ name }},"
                    "alh={{ alh }},"
                    "gda_name={{ gda_name }},"
                    "gda_desc={{ gda_desc }},"
                    "SPORT={{ SPORT }},"
                    "HOME={{ HOME }},"
                    "PMAC={{ PMAC }},"
                    "ALLOW_HOMED_SET={{ ALLOW_HOMED_SET }}"
                ),
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
