from pathlib import Path

from ruamel.yaml import YAML

from ibek.builder import Builder, Database, Entity, ObjectArg, StrArg


def test_deserialize_builder() -> None:
    expected = Builder(
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
                        file="pmac_asyn_motor.template", define_args="PMAC={{ PMAC.P }}"
                    ),
                ),
            ),
        ),
    )
    with open(Path(__file__).parent / "builder.yaml") as f:
        actual = Builder.deserialize(YAML().load(f))
    assert actual == expected
