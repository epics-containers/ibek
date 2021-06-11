from pathlib import Path

from apischema.utils import Undefined
from ruamel.yaml import YAML

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
                "pmacCreateController({{name}}, {{port}}, 0, 8, {{movingPoll}}, "
                "{{idlePoll}})",
                "pmacCreateAxes({{name}}, 8)",
            ),
        ),
        Entity(
            name="PmacAsynIPPort",
            args=(
                StrArg(
                    name="port",
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
                'PMACAsynIPPort({{port}}, {{IP + "" if ":" in IP else IP + ":1025"}})',
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


def test_deserialize_support() -> None:
    with open(Path(__file__).parent / "pmac.ibek.yaml") as f:
        actual = Support.deserialize(YAML().load(f))
    assert actual == SUPPORT


def test_format_script_on_entity() -> None:
    with open(Path(__file__).parent / "pmac.ibek.yaml") as f:
        actual = Support.deserialize(YAML().load(f))

    pmacIP = actual.entities[1]
    script = pmacIP.format_script(port="blah", IP="1.1.1.1")
    assert script == "PMACAsynIPPort(blah, 1.1.1.1:1025)"
