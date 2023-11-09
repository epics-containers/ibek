import os
from pathlib import Path

from pytest import fixture
from ruamel.yaml import YAML
from typer.testing import CliRunner

os.environ["EPICS_ROOT"] = str(Path(__file__).parent / "samples" / "epics")

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
def yaml_defs(samples):
    return samples / "yaml"


@fixture
def objects_classes(yaml_defs):
    # clear the entity classes to make sure there's nothing left
    clear_entity_model_ids()

    objects_support = get_support(yaml_defs / "objects.ibek.support.yaml")

    # make entity subclasses for everything defined in it
    namespace = make_entity_models(objects_support)

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
