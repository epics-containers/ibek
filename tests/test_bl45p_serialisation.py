from pathlib import Path

from ruamel.yaml import YAML

from ibek.pmac import EntityInstance, PmacAsynIPPort, PmacIOC

BL45P_MO_01 = PmacIOC(
    instances=(
        EntityInstance(
            type="pmac.pmacIOC",
            name="BRICK1port",
            IP=PmacAsynIPPort("192.168.0.12:1111"),
        ),
        EntityInstance(
            type="pmac.pmacIOC",
            name="BRICK3port",
            IP=PmacAsynIPPort("192.168.0.12:1113"),
        ),
        EntityInstance(
            type="pmac.pmacIOC",
            name="BRICK2port",
            IP=PmacAsynIPPort("192.168.0.12:1112"),
        ),
        EntityInstance(
            type="pmac.pmacIOC",
            name="BRICK4port",
            IP=PmacAsynIPPort("192.168.0.12:1114"),
        ),
        EntityInstance(
            type="pmac.pmacIOC", name="BRICK5port", IP=PmacAsynIPPort("192.168.0.12")
        ),
        EntityInstance(
            type="pmac.pmacIOC", name="BRICK6port", IP=PmacAsynIPPort("192.168.0.13")
        ),
    )
)


def test_deserialize_bl45p() -> None:
    with open(Path(__file__).parent / "bl45p-mo-ioc-02.yaml") as f:
        actual = PmacIOC.deserialize(YAML().load(f))
    assert actual == BL45P_MO_01

