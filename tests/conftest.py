from pathlib import Path

from pytest import fixture
from ruamel.yaml import YAML

from ibek.ioc import clear_entity_classes, make_entity_classes
from ibek.support import Support


@fixture
def samples():
    return Path(__file__).parent / "samples"


@fixture
def pmac_support(samples):
    # load from file
    d = YAML().load(samples / "yaml" / "pmac.ibek.yaml")
    # create a support object from that dict
    support = Support.deserialize(d)
    return support


@fixture
def pmac_classes(pmac_support):
    # clear the entity classes to make sure there's nothing left
    clear_entity_classes()

    # make entity subclasses for everything defined in it
    namespace = make_entity_classes(pmac_support)

    # return the namespace so that callers have access to all of the
    # generated dataclasses
    return namespace
