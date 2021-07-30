from pathlib import Path

from ruamel.yaml import YAML

from ibek.pmac import DlsPmacAsynMotor, Geobrick, PmacAsynIPPort, PmacIOC

sample_yaml = Path(__file__).parent / "samples" / "yaml"

BL45P_MO_IOC_02 = PmacIOC(
    ioc_name="BL45P_MO_IOC_02",
    instances=(
        PmacAsynIPPort(
            name="BRICK1port", type="pmac.PmacAsynIPPort", IP="192.168.0.12:1112"
        ),
        Geobrick(
            name="BL45P-MO-BRICK-01",
            type="pmac.Geobrick",
            port="BRICK1port",
            P="BL45P-MO-STEP-01:",
            idlePoll=100,
            movingPoll=500,
        ),
        DlsPmacAsynMotor(
            pmac="BL45P-MO-BRICK-01",
            type="pmac.DlsPmacAsynMotor",
            P="BL45P-MO-THIN-01:X1",
            axis=1,
        ),
    ),
)


def test_deserialize_bl45p() -> None:
    with open(sample_yaml / "bl45p-mo-ioc-02.pmac.yaml") as f:
        d = YAML().load(f)
        actual = PmacIOC.deserialize(d)
    assert actual == BL45P_MO_IOC_02
