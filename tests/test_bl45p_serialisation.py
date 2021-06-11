from pathlib import Path

from ruamel.yaml import YAML

from ibek.pmac import DlsPmacAsynMotor, Geobrick, PmacAsynIPPort, PmacIOC

BL45P_MO_IOC_02 = PmacIOC(
    ioc_name="BL45P_MO_IOC_02",
    instances=(
        PmacAsynIPPort(
            name="BRICK1port", type="pmac.PmacAsynIPPort", IP="192.168.0.12:1112"
        ),
        PmacAsynIPPort(
            name="BRICK2port", type="pmac.PmacAsynIPPort", IP="192.168.0.12:1112"
        ),
        PmacAsynIPPort(
            name="BRICK3port", type="pmac.PmacAsynIPPort", IP="192.168.0.12:1113"
        ),
        PmacAsynIPPort(
            name="BRICK4port", type="pmac.PmacAsynIPPort", IP="192.168.0.12:1114"
        ),
        PmacAsynIPPort(
            name="BRICK5port", type="pmac.PmacAsynIPPort", IP="192.168.0.12"
        ),
        PmacAsynIPPort(
            name="BRICK6port", type="pmac.PmacAsynIPPort", IP="192.168.0.13"
        ),
        Geobrick(
            name="BL45P-MO-BRICK-01",
            type="pmac.Geobrick",
            PORT="BRICK1port",
            P="BL45P-MO-STEP-01:",
            IdlePoll=100,
            movingPoll=500,
        ),
        DlsPmacAsynMotor(
            name="AxisOne",
            type="pmac.DlsPmacAsynMotor",
            P="BL45P-MO-MIRR-01:X1",
            axis=1,
        ),
    ),
)


def test_deserialize_bl45p() -> None:
    with open(Path(__file__).parent / "bl45p-mo-ioc-02.pmac.yaml") as f:
        actual = PmacIOC.deserialize(YAML().load(f))
    assert actual == BL45P_MO_IOC_02
