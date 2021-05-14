from ibek.pmac import PmacIOC
from pathlib import Path

from ruamel.yaml import YAML

BL45P_MO_01 = ""


def test_deserialize_bl45p() -> None:
    with open(Path(__file__).parent / "bl45p-mo-ioc-02.yaml") as f:
        actual = PmacIOC.deserialize(YAML().load(f))
    assert actual == BL45P_MO_01
