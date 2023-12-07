import os
from pathlib import Path

from pytest import fixture
from ruamel.yaml import YAML
from typer.testing import CliRunner

# This must be above the following imports so that it takes effect before
# `globals.EPICS_ROOT` is imported (or anything built on top of it)
os.environ["EPICS_ROOT"] = str(Path(__file__).parent / "samples" / "epics")

# The `noqa`s on these imports are necessary because of the above
from ibek.__main__ import cli  # noqa: E402
from ibek.ioc import clear_entity_model_ids, make_entity_models  # noqa: E402
from ibek.support import Support  # noqa: E402

runner = CliRunner()


def run_cli(*args):
    result = runner.invoke(cli, [str(x) for x in args])
    if result.exception:
        raise result.exception
    assert result.exit_code == 0, result


def get_support(yaml_file: str) -> Support:
    """
    Get a support object from the sample YAML directory
    """
    # load from file
    d = YAML(typ="safe").load(yaml_file)
    # create a support object from that dict
    support = Support(**d)
    return support


@fixture
def templates():
    return Path(__file__).parent.parent / "src" / "ibek" / "templates"


@fixture
def samples():
    return Path(__file__).parent / "samples"


@fixture
def support_defs(samples):
    return samples / "support"


@fixture
def ioc_defs(samples):
    return samples / "iocs"


@fixture
def asyn_classes(support_defs):
    # clear the entity classes to make sure there's nothing left
    clear_entity_model_ids()

    asyn_support = get_support(support_defs / "asyn.ibek.support.yaml")

    # make entity subclasses for everything defined in it
    namespace = make_entity_models(asyn_support)

    # return the namespace so that callers have access to all of the
    # generated dataclasses
    return namespace


@fixture
def motor_classes(support_defs):
    # clear the entity classes to make sure there's nothing left
    clear_entity_model_ids()

    asyn_support = get_support(support_defs / "asyn.ibek.support.yaml")
    motor_support = get_support(support_defs / "motorSim.ibek.support.yaml")

    # make entity subclasses for everything defined in it
    namespace = make_entity_models(asyn_support)
    namespace.extend(make_entity_models(motor_support))

    # return the namespace so that callers have access to all of the
    # generated dataclasses
    return namespace
