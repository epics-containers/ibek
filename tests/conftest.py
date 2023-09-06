from pathlib import Path

from pytest import fixture
from ruamel.yaml import YAML
from typer.testing import CliRunner

from ibek.__main__ import cli
from ibek.ioc import clear_entity_model_ids, make_entity_models
from ibek.support import Support

runner = CliRunner()


def run_cli(*args):
    result = runner.invoke(cli, [str(x) for x in args])
    if result.exception:
        raise result.exception
    assert result.exit_code == 0, result


def get_support(samples: Path, yaml_file: str) -> Support:
    """
    Get a support object from the sample YAML directory
    """
    # load from file
    d = YAML(typ="safe").load(samples / f"{yaml_file}")
    # create a support object from that dict
    support = Support(**d)
    return support


@fixture
def ibek_defs():
    return Path(__file__).parent.parent / "ibek-defs"


@fixture
def samples():
    return Path(__file__).parent / "samples"


@fixture
def pmac_support(ibek_defs):
    return get_support(ibek_defs / "pmac", "pmac.ibek.support.yaml")


@fixture
def pmac_classes(pmac_support):
    # clear the entity classes to make sure there's nothing left
    clear_entity_model_ids()

    # make entity subclasses for everything defined in it
    namespace = make_entity_models(pmac_support)

    # return the namespace so that callers have access to all of the
    # generated dataclasses
    return namespace


@fixture
def epics_support(ibek_defs):
    return get_support(ibek_defs / "_global", "epics.ibek.support.yaml")


@fixture
def epics_classes(epics_support):
    # clear the entity classes to make sure there's nothing left
    clear_entity_model_ids()

    # make entity subclasses for everything defined in it
    namespace = make_entity_models(epics_support)

    # return the namespace so that callers have access to all of the
    # generated dataclasses
    return namespace
