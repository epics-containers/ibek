from pathlib import Path

# I would use black but there is no API yet
from autopep8 import fix_code
from ruamel.yaml import YAML

from ibek.dataclass_from_yaml import yaml_to_dataclass

sample_yaml = Path(__file__).parent / "samples" / "yaml"


BL45P_MO_IOC_02 = fix_code(
    """pmac(
    ioc_name='BL45P_MO_IOC_02',
    instances=(
        pmac.PmacAsynIPPort(
            type='pmac.PmacAsynIPPort',
            name='BRICK1port',
            IP='192.168.0.12:1112'),
        pmac.Geobrick(
            type='pmac.Geobrick',
            name='BL45P-MO-BRICK-01',
            port='BRICK1port',
            P='BL45P-MO-STEP-01:',
            idlePoll=100,
            movingPoll=500),
        pmac.DlsPmacAsynMotor(
            type='pmac.DlsPmacAsynMotor',
            pmac='BL45P-MO-BRICK-01',
            axis=1,
            P='BL45P-MO-THIN-01:X1')))
""",
    options={"aggressive": 1},
)


def generate_pmac_classes():
    # create a support object from YAML
    support = yaml_to_dataclass(str(sample_yaml / "pmac.ibek.yaml"))

    # populate its dataclass namespace
    support.get_module_dataclass()

    # return the namespace so that callers have access to all of the
    # generated dataclasses
    return support.namespace


def test_deserialize_bl45p() -> None:
    namespace = generate_pmac_classes()

    pmac_ioc_cls = namespace["pmac"]

    with open(sample_yaml / "bl45p-mo-ioc-02.pmac.yaml") as f:
        d = YAML().load(f)
        code = pmac_ioc_cls.deserialize(d)
        actual = fix_code(str(code), options={"aggressive": 1})
    assert actual == BL45P_MO_IOC_02
