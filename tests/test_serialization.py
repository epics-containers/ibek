from pathlib import Path

from ruamel.yaml import YAML

from ibek.support import Database, Entity, ObjectArg, StrArg, Support

SUPPORT = Support(
    module="pmac",
    entities=(
        Entity(
            name="PMAC",
            args=(StrArg(name="PORT", description="Asyn port name", is_id=True),),
            script="PMACPortConfigure({{ PORT }}, 100)​",
        ),
        Entity(
            name="motor",
            args=(
                ObjectArg(
                    name="PMAC", type="pmac.PMAC", description="PMAC to attach to"
                ),
            ),
            databases=(
                Database(
                    file="pmac_asyn_motor.template", define_args="PORT={{ PMAC.PORT }}"
                ),
            ),
        ),
    ),
)


def test_deserialize_support() -> None:
    with open(Path(__file__).parent / "pmac.ibek.yaml") as f:
        actual = Support.deserialize(YAML().load(f))
    assert actual == SUPPORT


def test_format_script_on_entity() -> None:
    pmac = SUPPORT.entities[0]
    assert pmac.format_script(PORT="blah") == "PMACPortConfigure(blah, 100)​"
