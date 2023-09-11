"""
Tests to verify that the error handling works as expected.
"""
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from ibek.ioc import clear_entity_model_ids, make_entity_models, make_ioc_model
from ibek.support import Support
from tests.conftest import run_cli


def test_counter(tmp_path: Path, samples: Path):
    """
    Check you cannot redefine a counter with the same name and different params
    """

    clear_entity_model_ids()
    entity_file = samples / "yaml" / "bad_counter.ibek.ioc.yaml"
    definition_file1 = samples / "yaml" / "bad_counter.ibek.support.yaml"

    with pytest.raises(ValueError) as ctx:
        run_cli("build-startup", entity_file, definition_file1)
    assert (
        str(ctx.value)
        == "Redefining counter InterruptVector with different start/stop values"
    )


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
        run_cli("build-startup", entity_file, definition_file1)

    assert "Field required [type=missing" in str(ctx.value)
    assert "entities.0.`object_module.RefObject`.name" in str(ctx.value)
