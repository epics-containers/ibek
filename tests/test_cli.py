import json
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


def run_cli(*args):
    result = runner.invoke(cli, [str(x) for x in args])
    if result.exception:
        raise result.exception
    assert result.exit_code == 0, result


def test_builder_schema(tmp_path: Path, samples: Path):
    """generate the global ibek schema"""
    schema_path = tmp_path / "schema.json"
    run_cli("ibek-schema", schema_path)
    expected = json.loads((samples / "schemas" / "ibek.defs.schema.json").read_text())
    # Don't care if version number didn't update to match if the rest is the same
    # expected["title"] = mock.ANY

    actual = json.loads((schema_path).read_text())
    assert expected == actual


def test_pmac_schema(tmp_path: Path, samples: Path):
    """generate schema from the pmac support module definition yaml"""
    clear_entity_classes()

    schema_path = tmp_path / "pmac.ibek.entities.schema.json"
    yaml_path = samples / "yaml" / "pmac.ibek.support.yaml"
    run_cli("ioc-schema", yaml_path, schema_path)

    expected = json.loads(
        (samples / "schemas" / "pmac.ibek.entities.schema.json").read_text()
    )

    actual = json.loads((schema_path).read_text())
    assert expected == actual


def test_asyn_schema(tmp_path: Path, samples: Path):
    """generate schema from the asyn support module definition yaml"""
    clear_entity_classes()

    schema_path = tmp_path / "asyn.ibek.entities.schema.json"
    yaml_path = samples / "yaml" / "asyn.ibek.support.yaml"
    run_cli("ioc-schema", yaml_path, schema_path)

    expected = json.loads(
        (samples / "schemas" / "asyn.ibek.entities.schema.json").read_text()
    )

    actual = json.loads((schema_path).read_text())
    assert expected == actual


def test_container_schema(tmp_path: Path, samples: Path):
    clear_entity_classes()
    """generate schema for a container with two support modules"""

    schema_combined = tmp_path / "container.ibek.entities.schema.json"
    yaml_path1 = samples / "yaml" / "asyn.ibek.support.yaml"
    yaml_path2 = samples / "yaml" / "pmac.ibek.support.yaml"
    run_cli("ioc-schema", yaml_path1, yaml_path2, schema_combined)

    expected = json.loads(
        (samples / "schemas" / "container.ibek.entities.schema.json").read_text()
    )

    actual = json.loads((schema_combined).read_text())
    assert expected == actual


def test_build_startup_output_path(tmp_path: Path, samples: Path):
    """
    build an ioc startup script and ensure output directory gets generated
    if it doesn't pre-exist
    """
    clear_entity_classes()
    entity_file = samples / "yaml" / "bl45p-mo-ioc-02.ibek.entities.yaml"
    definition_file = samples / "yaml" / "pmac.ibek.support.yaml"
    out_file = tmp_path / "new_dir" / "st.cmd"
    out_db = tmp_path / "new_dir" / "make_db.sh"

    run_cli(
        "build-startup",
        entity_file,
        definition_file,
        "--out",
        out_file,
        "--db-out",
        out_db,
    )

    example_boot = (samples / "boot_scripts" / "st.cmd").read_text()
    actual_boot = out_file.read_text()

    assert example_boot == actual_boot


def test_build_startup_single(tmp_path: Path, samples: Path):
    """
    build an ioc startup script from an IOC instance entity file
    and a single support module definition file
    """
    clear_entity_classes()
    entity_file = samples / "yaml" / "bl45p-mo-ioc-02.ibek.entities.yaml"
    definition_file = samples / "yaml" / "pmac.ibek.support.yaml"
    out_file = tmp_path / "st.cmd"
    out_db = tmp_path / "make_db.sh"

    run_cli(
        "build-startup",
        entity_file,
        definition_file,
        "--out",
        out_file,
        "--db-out",
        out_db,
    )

    example_boot = (samples / "boot_scripts" / "st.cmd").read_text()
    actual_boot = out_file.read_text()

    assert example_boot == actual_boot


def test_build_startup_multiple(tmp_path: Path, samples: Path):
    """
    build an ioc startup script from an IOC instance entity file
    and multiple support module definition files
    """
    clear_entity_classes()
    entity_file = samples / "yaml" / "bl45p-mo-ioc-03.ibek.entities.yaml"
    definition_file1 = samples / "yaml" / "asyn.ibek.support.yaml"
    definition_file2 = samples / "yaml" / "pmac.ibek.support.yaml"
    out_file = tmp_path / "st.cmd"
    out_db = tmp_path / "make_db.sh"

    run_cli(
        "build-startup",
        entity_file,
        definition_file1,
        definition_file2,
        "--out",
        out_file,
        "--db-out",
        out_db,
    )

    example_boot = (samples / "boot_scripts" / "stbl45p-mo-ioc-03").read_text()
    actual_boot = out_file.read_text()

    assert example_boot == actual_boot


def test_build_startup_env_vars_and_post_ioc_init(tmp_path: Path, samples: Path):
    """
    build an ioc startup script from an IOC instance entity file, multiple
    support module definition files which include environment variables and
    post iocInit() entries
    """
    clear_entity_classes()
    entity_file = samples / "yaml" / "bl45p-mo-ioc-04.ibek.entities.yaml"
    definition_file1 = samples / "yaml" / "epics.ibek.support.yaml"
    definition_file2 = samples / "yaml" / "pmac.ibek.support.yaml"
    out_file = tmp_path / "st.cmd"
    out_db = tmp_path / "make_db.sh"

    run_cli(
        "build-startup",
        entity_file,
        definition_file1,
        definition_file2,
        "--out",
        out_file,
        "--db-out",
        out_db,
    )

    example_boot = (samples / "boot_scripts" / "stbl45p-mo-ioc-04").read_text()
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
    definition_file = samples / "yaml" / "pmac.ibek.support.yaml"
    support = Support.deserialize(YAML(typ="safe").load(definition_file))
    make_entity_classes(support)
    with pytest.raises(AssertionError) as ctx:
        make_entity_classes(support)
    assert str(ctx.value) == "Entity classes already created for pmac"
