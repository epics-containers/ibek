"""
The folder test/samples/black is used for formatting generated code for
and generating the files in test/samples/classes

This preamble file is added to the head of the generated class
"""

from apischema import Undefined

from ibek.support import (
    Database,
    Definition,
    FloatArg,
    IntArg,
    ObjectArg,
    StrArg,
    Support,
)

"""
This represents the generated instance of a Support Object which is an
object graph of Entity instandes. It is the product of deserializing
pmac.ibek.yaml
"""

# NOTE when the schema changes slightly you can re-create this file by breaking
# into the test_deserialize_support and pasting the value of 'actual' here
# afterward run (I did this from a peer dir with latest black in its pipenv):
#    pipenv run black --experimental-string-processing ../ibek/tests/samples/classes

SUPPORT = Support(
    module="pmac",
    definitions=(
        Definition(
            name="Geobrick",
            args=(
                StrArg(
                    name="name",
                    description="Name to use for the geobrick's asyn port",
                    type="str",
                    default=Undefined,
                    is_id=False,
                ),
                ObjectArg(
                    name="PORT",
                    description="Asyn port name for PmacAsynIPPort to connect to",
                    type="pmac.PmacAsynIPPort",
                    default=Undefined,
                ),
                StrArg(
                    name="P",
                    description="PV Prefix for all pmac db templates",
                    type="str",
                    default=Undefined,
                    is_id=False,
                ),
                IntArg(
                    name="numAxes",
                    description="number of axes to initialize for the controller",
                    type="int",
                    default=Undefined,
                ),
                IntArg(
                    name="idlePoll",
                    description="Idle Poll Period in ms",
                    type="int",
                    default=Undefined,
                ),
                IntArg(
                    name="movingPoll",
                    description="Moving Poll Period in ms",
                    type="int",
                    default=Undefined,
                ),
            ),
            databases=(
                Database(
                    file="pmacController.template",
                    include_args=(),
                    define_args="PMAC={{ P }}",
                ),
                Database(
                    file="pmacStatus.template",
                    include_args=(),
                    define_args="PMAC={{ P }}",
                ),
            ),
            script=(
                "pmacCreateController({{name}}, {{PORT.name}}, 0, {{numAxes}},"
                " {{movingPoll}}, {{idlePoll}})",
                "pmacCreateAxes({{name}}, {{numAxes}})",
            ),
        ),
        Definition(
            name="PmacAsynIPPort",
            args=(
                StrArg(
                    name="name",
                    description="Asyn port name",
                    type="str",
                    default=Undefined,
                    is_id=True,
                ),
                StrArg(
                    name="IP",
                    description="IP address of pmac",
                    type="str",
                    default=Undefined,
                    is_id=False,
                ),
            ),
            databases=(),
            script=(
                'pmacAsynIPConfigure({{name}}, {{IP if ":" in IP else IP + ":1025"}})',
            ),
        ),
        Definition(
            name="DlsPmacAsynMotor",
            args=(
                StrArg(
                    name="PMAC",
                    description="PMAC to attach to",
                    type="str",
                    default=Undefined,
                    is_id=False,
                ),
                IntArg(
                    name="axis",
                    description="which axis number this motor drives",
                    type="int",
                    default=Undefined,
                ),
                StrArg(
                    name="P",
                    description="PV prefix name for this motor",
                    type="str",
                    default=Undefined,
                    is_id=False,
                ),
                StrArg(
                    name="M",
                    description="PV motor name for this motor",
                    type="str",
                    default=Undefined,
                    is_id=False,
                ),
                StrArg(
                    name="PORT",
                    description="Delta tau motor controller",
                    type="str",
                    default=Undefined,
                    is_id=False,
                ),
                StrArg(
                    name="SPORT",
                    description="Delta tau motor controller comms port",
                    type="str",
                    default=Undefined,
                    is_id=False,
                ),
                StrArg(
                    name="name",
                    description="Object name and gui association name",
                    type="str",
                    default=Undefined,
                    is_id=False,
                ),
                StrArg(
                    name="DESC",
                    description="Description, displayed on EDM screen",
                    type="str",
                    default="",
                    is_id=False,
                ),
                FloatArg(
                    name="MRES",
                    description="Motor Step Size (EGU)",
                    type="float",
                    default=0.0001,
                ),
                FloatArg(
                    name="VELO",
                    description="axis Velocity (EGU/s)",
                    type="float",
                    default=1.0,
                ),
                FloatArg(
                    name="PREC",
                    description="Display Precision",
                    type="float",
                    default=3.0,
                ),
                StrArg(
                    name="EGU",
                    description="Engineering Units",
                    type="str",
                    default="mm",
                    is_id=False,
                ),
                IntArg(
                    name="TWV",
                    description="Tweak Step Size (EGU)",
                    type="int",
                    default=1,
                ),
                StrArg(
                    name="DTYP",
                    description="Datatype of record",
                    type="str",
                    default="asynMotor",
                    is_id=False,
                ),
                IntArg(name="DIR", description="User direction", type="int", default=0),
                FloatArg(
                    name="VBAS",
                    description="Base Velocity (EGU/s)",
                    type="float",
                    default=1.0,
                ),
                StrArg(
                    name="VMAX",
                    description="Max Velocity (EGU/s)",
                    type="str",
                    default="$(VELO)",
                ),
                FloatArg(
                    name="ACCL",
                    description="Seconds to Velocity",
                    type="float",
                    default=0.5,
                ),
                FloatArg(
                    name="BDST",
                    description="BL Distance (EGU)",
                    type="float",
                    default=0.0,
                ),
                FloatArg(
                    name="BVEL",
                    description="BL Velocity(EGU/s)",
                    type="float",
                    default=0.0,
                ),
                FloatArg(
                    name="BACC",
                    description="BL Seconds to Veloc",
                    type="float",
                    default=0.0,
                ),
                FloatArg(
                    name="DHLM",
                    description="Dial High Limit",
                    type="float",
                    default=10000.0,
                ),
                FloatArg(
                    name="DLMM",
                    description="Dial low limit",
                    type="float",
                    default=-10000.0,
                ),
                FloatArg(
                    name="HLM", description="User High Limit", type="float", default=0.0
                ),
                FloatArg(
                    name="LLM", description="User Low Limit", type="float", default=0.0
                ),
                StrArg(
                    name="HLSV",
                    description="HW Lim, Violation Svr",
                    type="str",
                    default="MAJOR",
                    is_id=False,
                ),
                StrArg(
                    name="INIT",
                    description="Startup commands",
                    type="str",
                    default="",
                    is_id=False,
                ),
                FloatArg(
                    name="SREV",
                    description="Steps per Revolution",
                    type="float",
                    default=1000.0,
                ),
                FloatArg(
                    name="RRES",
                    description="Readback Step Size (EGU",
                    type="float",
                    default=0.0,
                ),
                FloatArg(
                    name="ERES",
                    description="Encoder Step Size (EGU)",
                    type="float",
                    default=0.0,
                ),
                FloatArg(
                    name="JAR",
                    description="Jog Acceleration (EGU/s^2)",
                    type="float",
                    default=0.0,
                ),
                IntArg(
                    name="UEIP",
                    description="Use Encoder If Present",
                    type="int",
                    default=0,
                ),
                IntArg(
                    name="URIP",
                    description="Use RDBL If Present",
                    type="int",
                    default=0,
                ),
                StrArg(
                    name="RDBL",
                    description="Readback Location, set URIP =1 if you specify this",
                    type="str",
                    default="0",
                    is_id=False,
                ),
                StrArg(
                    name="RLNK",
                    description="Readback output link",
                    type="str",
                    default="",
                    is_id=False,
                ),
                IntArg(
                    name="RTRY", description="Max retry count", type="int", default=0
                ),
                FloatArg(
                    name="DLY",
                    description="Readback settle time (s)",
                    type="float",
                    default=0.0,
                ),
                FloatArg(
                    name="OFF",
                    description="User Offset (EGU)",
                    type="float",
                    default=0.0,
                ),
                FloatArg(
                    name="RDBD",
                    description="Retry Deadband (EGU)",
                    type="float",
                    default=0.0,
                ),
                IntArg(
                    name="FOFF",
                    description="Freeze Offset, 0=variable, 1=frozen",
                    type="int",
                    default=0,
                ),
                FloatArg(
                    name="ADEL",
                    description="Alarm monitor deadband (EGU)",
                    type="float",
                    default=0.0,
                ),
                IntArg(
                    name="NTM",
                    description="New Target Monitor, only set to 0 for soft motors",
                    type="int",
                    default=1,
                ),
                FloatArg(
                    name="FEHEIGH",
                    description="HIGH limit for following error",
                    type="float",
                    default=0.0,
                ),
                FloatArg(
                    name="FEHIHI",
                    description="HIHI limit for following error",
                    type="float",
                    default=0.0,
                ),
                StrArg(
                    name="FEHHSV",
                    description="HIHI alarm severity for following error",
                    type="str",
                    default="NO_ALARM",
                    is_id=False,
                ),
                StrArg(
                    name="FEHSV",
                    description="HIGH alarm severity for following error",
                    type="str",
                    default="NO_ALARM",
                    is_id=False,
                ),
                IntArg(name="SCALE", description="", type="int", default=1),
                IntArg(
                    name="HOMEVIS",
                    description="If 1 then home is visible on the gui",
                    type="int",
                    default=1,
                ),
                StrArg(
                    name="HOMEVISST",
                    description="",
                    type="str",
                    default="Use motor summary screen",
                    is_id=False,
                ),
                StrArg(
                    name="alh",
                    description=(
                        "Set this to alh to add the motor to the alarm handler and send"
                        " emails"
                    ),
                    type="str",
                    default="",
                    is_id=False,
                ),
                StrArg(
                    name="gda_name",
                    description="Name to export this as to GDA",
                    type="str",
                    default="none",
                    is_id=False,
                ),
                StrArg(
                    name="gda_desc",
                    description="Description to export as to GDA",
                    type="str",
                    default="$(DESC)",
                    is_id=False,
                ),
                StrArg(
                    name="HOME",
                    description=(
                        "Prefix for autohome instance. Defaults to $(P) If unspecified"
                    ),
                    type="str",
                    default="$(P)",
                    is_id=False,
                ),
                StrArg(
                    name="ALLOW_HOMED_SET",
                    description="Set to a blank to allow this axis to have its homed",
                    type="str",
                    default="#",
                    is_id=False,
                ),
            ),
            databases=(
                Database(
                    file="$(PMAC)/db/dls_pmac_asyn_motor.template",
                    include_args=(
                        "P",
                        "M",
                        "PORT",
                        "DESC",
                        "MRES",
                        "VELO",
                        "PREC",
                        "EGU",
                        "TWV",
                        "DTYP",
                        "DIR",
                        "VBAS",
                        "VMAX",
                        "ACCL",
                        "BDST",
                        "BVEL",
                        "BACC",
                        "DHLM",
                        "DLLM",
                        "HLM",
                        "LLM",
                        "HLSV",
                        "INIT",
                        "SREV",
                        "RRES",
                        "ERES",
                        "JAR",
                        "UEIP",
                        "RDBL",
                        "RLINK",
                        "RTRY",
                        "DLY",
                        "OFF",
                        "RDBD",
                        "FOFF",
                        "ADEL",
                        "NTM",
                        "FEHIGH",
                        "FEHIHI",
                        "FEHHSV",
                        "FEHSV",
                        "SCALE",
                        "HOMEVIS",
                        "HOMEVISSTR",
                        "name",
                        "alh",
                        "gda_name",
                        "gda_desc",
                        "SPORT",
                        "HOME",
                        "PMAC",
                        "ALLOW_HOMED_SET",
                    ),
                    define_args="ADDR={{ axis }}\n",
                ),
            ),
            script=(),
        ),
    ),
)
