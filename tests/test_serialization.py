from pathlib import Path

from ruamel.yaml import YAML

from ibek.support import Database, Entity, ObjectArg, StrArg, Support

SUPPORT = Support(
    module="asyn",
    entities=(
        Entity(
            name="AsynIP",
            args=(
                StrArg(name="name", description="Asyn port name", is_id=True),
                StrArg(name="port", description="Asyn port number"),
            ),
            script="PMACAsynIPPort({{name}}, {{port}})​",
        ),
    ),
)


def test_deserialize_support() -> None:
    with open(Path(__file__).parent / "asyn.ibek.yaml") as f:
        actual = Support.deserialize(YAML().load(f))
    assert actual == SUPPORT


def test_format_script_on_entity() -> None:
    pmac = SUPPORT.entities[0]
    assert pmac.format_script(PORT="blah") == "PMACPortConfigure(blah, 100)​"
