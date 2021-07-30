from apischema.utils import Undefined

from ibek.support import Database, Entity, IntArg, StrArg, Support

SUPPORT = Support(
    module="pmac",
    entities=(
        Entity(
            name="Geobrick",
            args=(
                StrArg(
                    name="name",
                    description="Name to use for the geobrick's asyn port",
                    type="str",
                    default=Undefined,
                    is_id=True,
                ),
                StrArg(
                    name="port",
                    description="Asyn port name for PmacAsynIPPort to connect to",
                    type="str",
                    default=Undefined,
                    is_id=False,
                ),
                StrArg(
                    name="P",
                    description="PV Prefix for all pmac db templates",
                    type="str",
                    default=Undefined,
                    is_id=False,
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
                "pmacCreateController({{name}}, {{port}}, 0, 8, "
                "{{movingPoll}}, {{idlePoll}})",
                "pmacCreateAxes({{name}}, 8)",
            ),
        ),
        Entity(
            name="PmacAsynIPPort",
            args=(
                StrArg(
                    name="name",
                    description="Asyn port name",
                    type="str",
                    default=Undefined,
                    is_id=False,
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
                'pmacAsynIPConfigure({{name}}, {{IP + "" if ":" in '
                'IP else IP + ":1025"}})',
            ),
        ),
        Entity(
            name="DlsPmacAsynMotor",
            args=(
                StrArg(
                    name="pmac",
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
                    description="PV name for this motor",
                    type="str",
                    default=Undefined,
                    is_id=False,
                ),
            ),
            databases=(
                Database(
                    file="pmac_asyn_Motor.template",
                    include_args=(),
                    define_args="PMAC={{ pmac.P }}",
                ),
            ),
            script=(),
        ),
    ),
)
