import os
import shutil
from pathlib import Path

from pytest import fixture
from pytest_mock import MockerFixture
from ruamel.yaml import YAML
from typer.testing import CliRunner

from ibek.__main__ import cli
from ibek.entity_factory import EntityFactory
from ibek.globals import GLOBALS
from ibek.support import Support

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


# only one EntityFactory instance for each test
@fixture(scope="function")
def entity_factory():
    return EntityFactory()


@fixture
def tmp_epics_root(samples: Path, tmp_path: Path, mocker: MockerFixture):
    # create an partially populated epics_root structure in a temporary folder
    epics = tmp_path / "epics"
    epics_source = samples / "epics"
    epics.mkdir()
    # a dummy venv for testing extract_assets
    Path.mkdir(tmp_path / "venv")

    # create the minimal structure under epics root
    files = epics_source.glob("*")
    for f in files:
        if f.is_dir():
            shutil.copytree(f, epics / f.name)
        else:
            shutil.copy(f, epics / f.name)
    Path.mkdir(epics / "opi", exist_ok=True)
    Path.mkdir(epics / "epics-base", exist_ok=True)
    Path.mkdir(epics / "generic-source" / "ioc" / "config", parents=True)
    (epics / "ioc").symlink_to(epics / "generic-source" / "ioc")
    Path.mkdir(epics / "ibek-defs", exist_ok=True)
    Path.mkdir(epics / "runtime", exist_ok=True)

    # patch the global EPICS_ROOT to point to this temporary folder
    mocker.patch.object(GLOBALS, "_EPICS_ROOT", epics)

    # this should not be needed - what gives?
    os.environ["IOC"] = "/epics/ioc"
    os.environ["RUNTIME_DIR"] = "/epics/runtime"

    return epics


@fixture
def asyn_classes(support_defs, entity_factory):
    asyn_support = get_support(support_defs / "asyn.ibek.support.yaml")

    # make entity subclasses for everything defined in it
    namespace = entity_factory._make_entity_models(asyn_support)

    # return the namespace so that callers have access to all of the
    # generated dataclasses
    return namespace


@fixture
def motor_classes(support_defs, entity_factory):
    asyn_support = get_support(support_defs / "asyn.ibek.support.yaml")
    motor_support = get_support(support_defs / "motorSim.ibek.support.yaml")

    # make entity subclasses for everything defined in it
    namespace = entity_factory._make_entity_models(asyn_support)
    namespace.extend(entity_factory._make_entity_models(motor_support))

    # return the namespace so that callers have access to all of the
    # generated dataclasses
    return namespace
