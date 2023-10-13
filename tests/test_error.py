"""
Tests to verify that the error handling works as expected.
"""
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from ibek.ioc import clear_entity_model_ids, make_entity_models, make_ioc_model
from ibek.support import Support
from ibek.utils import UTILS
from tests.conftest import run_cli


def test_counter_reuse(tmp_path: Path, samples: Path):
    """
    Check you cannot redefine a counter with the same name and different params
    """
    UTILS.__reset__()

    entity_file = samples / "yaml" / "bad_counter.ibek.ioc.yaml"
    definition_file1 = samples / "yaml" / "utils.ibek.support.yaml"

    with pytest.raises(ValueError) as ctx:
        run_cli("runtime", "generate", entity_file, definition_file1)
    assert (
        str(ctx.value)
        == "Redefining counter InterruptVector with different start/stop values"
    )


def test_counter_overuse(tmp_path: Path, samples: Path):
    """
    Check that counter limits are enforced
    """
    UTILS.__reset__()

    entity_file = samples / "yaml" / "bad_counter2.ibek.ioc.yaml"
    definition_file1 = samples / "yaml" / "utils.ibek.support.yaml"

    with pytest.raises(ValueError) as ctx:
        run_cli("runtime", "generate", entity_file, definition_file1)
    assert str(ctx.value) == "Counter 195 exceeded stop value of 194"


def test_bad_ref(tmp_path: Path, samples: Path):
    """
    Check bad object references are caught
    """
    UTILS.__reset__()

    entity_file = samples / "yaml" / "bad_ref.ibek.ioc.yaml"
    definition_file1 = samples / "yaml" / "objects.ibek.support.yaml"
    definition_file2 = samples / "yaml" / "all.ibek.support.yaml"

    with pytest.raises(ValueError) as ctx:
        run_cli("runtime", "generate", entity_file, definition_file1, definition_file2)
    assert "object Ref2 not found" in str(ctx.value)


def test_bad_db(tmp_path: Path, samples: Path):
    """
    Check bad database args are caught
    """
    UTILS.__reset__()

    entity_file = samples / "yaml" / "bad_db.ibek.ioc.yaml"
    definition_file1 = samples / "yaml" / "bad_db.ibek.support.yaml"

    with pytest.raises(ValueError) as ctx:
        run_cli("runtime", "generate", entity_file, definition_file1)
    assert "'non-existant' in database template 'test.db' not found" in str(ctx.value)


def test_loading_module_twice(tmp_path: Path, samples: Path):
    """
    Verify we get a sensible error if we try to load a module twice
    without clearing the entity model ids
    """

    clear_entity_model_ids()

    definition_file = samples / "yaml" / "objects.ibek.support.yaml"
    instance_file = samples / "yaml" / "objects.ibek.ioc.yaml"

    support = Support(**YAML(typ="safe").load(definition_file))
    entities1 = make_entity_models(support)
    entities2 = make_entity_models(support)

    generic_ioc1 = make_ioc_model(entities1)
    generic_ioc2 = make_ioc_model(entities2)

    instance = YAML(typ="safe").load(instance_file)
    generic_ioc1(**instance)
    with pytest.raises(ValueError) as ctx:
        generic_ioc2(**instance)

    assert "Duplicate id" in str(ctx.value)


def test_defaults(tmp_path: Path, samples: Path):
    """
    Check you cannot redefine a counter with the same name and different params
    """

    clear_entity_model_ids()
    entity_file = samples / "yaml" / "bad_default.ibek.ioc.yaml"
    definition_file1 = samples / "yaml" / "objects.ibek.support.yaml"

    with pytest.raises(ValueError) as ctx:
        run_cli("runtime", "generate", entity_file, definition_file1)

    assert "Field required [type=missing" in str(ctx.value)
