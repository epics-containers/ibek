"""
Tests to verify that the error handling works as expected.
"""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from ibek.ioc_factory import IocFactory
from ibek.support import Support
from ibek.utils import UTILS
from tests.conftest import run_cli


def test_counter_overuse(tmp_epics_root: Path, samples: Path):
    """
    Check that counter limits are enforced
    """
    UTILS.__reset__()

    entity_file = samples / "iocs" / "bad_counter2.ibek.ioc.yaml"
    definition_file1 = samples / "support" / "utils.ibek.support.yaml"

    with pytest.raises(ValueError) as ctx:
        run_cli("runtime", "generate", entity_file, definition_file1)

    assert "Counter InterruptVector exceeded maximum value of 194" in str(ctx.value)


def test_bad_ref(samples: Path):
    """
    Check bad object references are caught
    """
    UTILS.__reset__()

    entity_file = samples / "iocs" / "bad_ref.ibek.ioc.yaml"
    definition_file1 = samples / "support" / "asyn.ibek.support.yaml"
    definition_file2 = samples / "support" / "motorSim.ibek.support.yaml"

    with pytest.raises(ValueError) as ctx:
        run_cli("runtime", "generate", entity_file, definition_file1, definition_file2)
    assert "object controllerOnePort_BAD_REF not found" in str(ctx.value)


def test_bad_db(tmp_epics_root: Path, samples: Path):
    """
    Check bad database args are caught
    """
    UTILS.__reset__()

    entity_file = samples / "iocs" / "bad_db.ibek.ioc.yaml"
    definition_file1 = samples / "support" / "bad_db.ibek.support.yaml"

    with pytest.raises(ValueError) as ctx:
        run_cli("runtime", "generate", entity_file, definition_file1)
    assert "'non-existant' in database template 'test.db' not found" in str(ctx.value)


def test_loading_module_twice(entity_factory, samples: Path):
    """
    Verify we get a sensible error if we try to load a module twice
    without clearing the entity model ids
    """
    definition_file = samples / "support" / "utils.ibek.support.yaml"
    instance_file = samples / "iocs" / "utils.ibek.ioc.yaml"

    support = Support(**YAML(typ="safe").load(definition_file))
    entities1 = entity_factory._make_entity_models(support)
    entities2 = entity_factory._make_entity_models(support)

    ioc_factory = IocFactory()
    generic_ioc1 = ioc_factory.make_ioc_model(entities1)
    generic_ioc2 = ioc_factory.make_ioc_model(entities2)

    instance = YAML(typ="safe").load(instance_file)
    generic_ioc1(**instance)
    with pytest.raises(ValueError) as ctx:
        generic_ioc2(**instance)

    assert "Duplicate id" in str(ctx.value)


def test_defaults(tmp_path: Path, samples: Path):
    """
    Check you cannot redefine a counter with the same name and different params
    """
    entity_file = samples / "iocs" / "bad_default.ibek.ioc.yaml"
    definition_file1 = samples / "support" / "asyn.ibek.support.yaml"

    with pytest.raises(ValueError) as ctx:
        run_cli("runtime", "generate", entity_file, definition_file1)

    assert "Field required [type=missing" in str(ctx.value)
