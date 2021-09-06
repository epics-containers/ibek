import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from ibek import __version__
from ibek.__main__ import cli
from ibek.ioc import clear_entity_classes, make_entity_classes
from ibek.support import Support

runner = CliRunner()


def test_version():
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0, f"ibek --version failed with: {result}"
    assert result.stdout == __version__ + "\n"


def test_builder_schema(tmp_path: Path, samples: Path):
    schema_path = tmp_path / "schema.json"
    result = runner.invoke(cli, ["ibek-schema", str(schema_path)])
    assert result.exit_code == 0, f"ibek-schema failed with: {result}"
    expected = json.loads(open(samples / "schemas" / "ibek.schema.json").read())
    # Don't care if version number didn't update to match if the rest is the same
    # expected["title"] = mock.ANY

    actual = json.loads(open(schema_path).read())
    assert expected == actual


def test_pmac_schema(tmp_path: Path, samples: Path):
    clear_entity_classes()

    schema_path = tmp_path / "pmac.ibek.schema.json"
    yaml_path = samples / "yaml" / "pmac.ibek.yaml"
    result = runner.invoke(cli, ["ioc-schema", str(yaml_path), str(schema_path)])
    assert result.exit_code == 0, f"ioc-schema failed with: {result}"

    expected = json.loads(open(samples / "schemas" / "pmac.schema.json").read())

    actual = json.loads(open(schema_path).read())
    assert expected == actual


def test_build_ioc(tmp_path: Path, samples: Path):
    clear_entity_classes()
    description = samples / "yaml" / "pmac.ibek.yaml"
    definition = samples / "yaml" / "bl45p-mo-ioc-02.pmac.yaml"

    result = runner.invoke(
        cli, ["build-ioc", str(description), str(definition), str(tmp_path)]
    )
    assert result.exit_code == 0, f"build-ioc failed with: {result}"

    example_boot = (samples / "helm" / "ioc.boot").read_text()
    actual_file = tmp_path / "bl45p-mo-ioc-02" / "config" / "ioc.boot"
    actual_boot = actual_file.read_text()

    assert example_boot == actual_boot

    # TODO check chart and values yaml files too


def test_loading_module_twice(tmp_path: Path, samples: Path):
    clear_entity_classes()
    # When we deserialize the same yaml twice as we do in the full test suite
    # we may get clashes in the namespace of generated Entity classes.
    # This tests that we get a sensible error when we do
    definition_file = samples / "yaml" / "pmac.ibek.yaml"
    support = Support.deserialize(YAML().load(definition_file))
    make_entity_classes(support)
    with pytest.raises(AssertionError) as ctx:
        make_entity_classes(support)
    assert str(ctx.value) == "Entity classes already created for pmac"
