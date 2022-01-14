import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from ibek import __version__
from ibek.__main__ import cli
from ibek.ioc import clear_entity_classes, make_entity_classes
from ibek.support import Support

runner = CliRunner()


def test_cli_version():
    cmd = [sys.executable, "-m", "ibek", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__


def test_builder_schema(tmp_path: Path, samples: Path):
    """generate the global ibek schema"""
    schema_path = tmp_path / "schema.json"
    result = runner.invoke(cli, ["ibek-schema", str(schema_path)])
    assert result.exit_code == 0, f"ibek-schema failed with: {result}"
    expected = json.loads(open(samples / "schemas" / "ibek.schema.json").read())
    # Don't care if version number didn't update to match if the rest is the same
    # expected["title"] = mock.ANY

    actual = json.loads(open(schema_path).read())
    assert expected == actual


def test_pmac_schema(tmp_path: Path, samples: Path):
    """generate schema from the pmac support module definition yaml"""
    clear_entity_classes()

    schema_path = tmp_path / "pmac.ibek.schema.json"
    yaml_path = samples / "yaml" / "pmac.ibek.yaml"
    result = runner.invoke(cli, ["ioc-schema", str(yaml_path), str(schema_path)])
    assert result.exit_code == 0, f"ioc-schema failed with: {result}"

    expected = json.loads(open(samples / "schemas" / "pmac.schema.json").read())

    actual = json.loads(open(schema_path).read())
    assert expected == actual


def test_asyn_schema(tmp_path: Path, samples: Path):
    """generate schema from the asyn support module definition yaml"""
    clear_entity_classes()

    schema_path = tmp_path / "asyn.ibek.schema.json"
    yaml_path = samples / "yaml" / "asyn.ibek.yaml"
    result = runner.invoke(cli, ["ioc-schema", str(yaml_path), str(schema_path)])
    assert result.exit_code == 0, f"ioc-schema failed with: {result}"

    expected = json.loads(open(samples / "schemas" / "asyn.schema.json").read())

    actual = json.loads(open(schema_path).read())
    assert expected == actual


def test_container_schema(tmp_path: Path, samples: Path):
    clear_entity_classes()
    """generate schema for a container with two support modules"""

    schema_combined = tmp_path / "container.schema.json"
    yaml_path1 = samples / "yaml" / "asyn.ibek.yaml"
    yaml_path2 = samples / "yaml" / "pmac.ibek.yaml"
    result = runner.invoke(
        cli, ["ioc-schema", str(yaml_path1), str(yaml_path2), str(schema_combined)]
    )
    assert result.exit_code == 0, f"ioc-schema failed with: {result}"

    expected = json.loads(open(samples / "schemas" / "container.schema.json").read())

    actual = json.loads(open(schema_combined).read())
    assert expected == actual


def test_build_helm(tmp_path: Path, samples: Path):
    """build an ioc helm chart from an IOC instance entity file"""
    clear_entity_classes()
    entity_file = samples / "yaml" / "bl45p-mo-ioc-02.pmac.yaml"

    os.chdir(str(samples))
    result = runner.invoke(cli, ["build-helm", str(entity_file), str(tmp_path)])
    assert result.exit_code == 0, f"build-ioc failed with: {result}"

    example_entity = entity_file.read_text()
    actual_file = tmp_path / "bl45p-mo-ioc-02" / "config" / "ioc.boot.yaml"
    actual_entity = actual_file.read_text()

    assert example_entity == actual_entity

    for test_file in ["Chart.yaml", "values.yaml"]:
        example = (samples / "helm" / test_file).read_text()
        actual_file = tmp_path / "bl45p-mo-ioc-02" / test_file
        actual = actual_file.read_text()

        assert example == actual


def test_build_startup_single(tmp_path: Path, samples: Path):
    """
    build an ioc startup script from an IOC instance entity file
    and a single support module definition file
    """
    clear_entity_classes()
    entity_file = samples / "yaml" / "bl45p-mo-ioc-02.pmac.yaml"
    definition_file = samples / "yaml" / "pmac.ibek.yaml"
    out_file = tmp_path / "ioc.boot"

    result = runner.invoke(
        cli, ["build-startup", str(entity_file), str(definition_file), str(out_file)]
    )
    assert result.exit_code == 0, f"build-ioc failed with: {result}"

    example_boot = (samples / "helm" / "ioc.boot").read_text()
    actual_boot = out_file.read_text()

    assert example_boot == actual_boot


def test_build_startup_multiple(tmp_path: Path, samples: Path):
    """
    build an ioc startup script from an IOC instance entity file
    and multiple support module definition files
    """
    clear_entity_classes()
    entity_file = samples / "yaml" / "bl45p-mo-ioc-03.pmac.yaml"
    definition_file1 = samples / "yaml" / "asyn.ibek.yaml"
    definition_file2 = samples / "yaml" / "pmac.ibek.yaml"
    out_file = tmp_path / "ioc.boot"

    result = runner.invoke(
        cli,
        [
            "build-startup",
            str(entity_file),
            str(definition_file1),
            str(definition_file2),
            str(out_file),
        ],
    )
    assert result.exit_code == 0, f"build-ioc failed with: {result}"

    example_boot = (samples / "helm" / "bl45p-mo-ioc-03.boot").read_text()
    actual_boot = out_file.read_text()

    assert example_boot == actual_boot


def test_build_startup_env_vars_and_post_ioc_init(tmp_path: Path, samples: Path):
    """
    build an ioc startup script from an IOC instance entity file, multiple
    support module definition files which include environment variables and
    post iocInit() entries
    """
    clear_entity_classes()
    entity_file = samples / "yaml" / "bl45p-mo-ioc-04.pmac.yaml"
    definition_file1 = samples / "yaml" / "epics.ibek.yaml"
    definition_file2 = samples / "yaml" / "pmac.ibek.yaml"
    out_file = tmp_path / "ioc.boot"

    result = runner.invoke(
        cli,
        [
            "build-startup",
            str(entity_file),
            str(definition_file1),
            str(definition_file2),
            str(out_file),
        ],
    )
    assert result.exit_code == 0, f"build-ioc failed with: {result}"

    example_boot = (samples / "helm" / "bl45p-mo-ioc-04.boot").read_text()
    actual_boot = out_file.read_text()

    assert example_boot == actual_boot


def test_loading_module_twice(tmp_path: Path, samples: Path):
    """
    regression test to demonstrate that clear_entity_classes works and
    allows us to call make_entity_classes more than once
    """

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
