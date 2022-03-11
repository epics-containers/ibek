from pathlib import Path

from pytest import fixture
from ruamel.yaml import YAML

from ibek.ioc import clear_entity_classes, make_entity_classes
from ibek.support import Support


def get_support(samples: Path, yaml_file: str) -> Support:
    """
    Get a support object from the sample YAML directory
    """
    # load from file
    d = YAML(typ="safe").load(samples / "yaml" / f"{yaml_file}")
    # create a support object from that dict
    support = Support.deserialize(d)
    return support


@fixture
def samples():
    return Path(__file__).parent / "samples"


@fixture
def pmac_support(samples):
    return get_support(samples, "pmac.ibek.defs.yaml")


@fixture
def pmac_classes(pmac_support):
    # clear the entity classes to make sure there's nothing left
    clear_entity_classes()

    # make entity subclasses for everything defined in it
    namespace = make_entity_classes(pmac_support)

    # return the namespace so that callers have access to all of the
    # generated dataclasses
    return namespace


@fixture
def epics_support(samples):
    return get_support(samples, "epics.ibek.defs.yaml")


@fixture
def epics_classes(epics_support):
    # clear the entity classes to make sure there's nothing left
    clear_entity_classes()

    # make entity subclasses for everything defined in it
    namespace = make_entity_classes(epics_support)

    # return the namespace so that callers have access to all of the
    # generated dataclasses
    return namespace
