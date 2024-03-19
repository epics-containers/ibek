"""
System tests that run the CLI commands and compare the output to expected
results.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from pytest_mock import MockerFixture

from ibek import __version__
from ibek.globals import (
    GLOBALS,
    PVI_YAML_PATTERN,
    SUPPORT_YAML_PATTERN,
)
from ibek.ioc import clear_entity_model_ids
from ibek.runtime_cmds.commands import generate
from ibek.support_cmds.commands import generate_links
from tests.conftest import run_cli


def test_cli_version():
    cmd = [sys.executable, "-m", "ibek", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__


def test_ibek_schema(tmp_path: Path, samples: Path):
    """generate the global ibek schema"""
    schema_path = tmp_path / "schema.json"
    run_cli("support", "generate-schema", "--output", schema_path)
    expected = json.loads(
        (samples / "schemas" / "ibek.support.schema.json").read_text()
    )

    actual = json.loads((schema_path).read_text())
    assert expected == actual


def test_single_schema(tmp_path: Path, samples: Path):
    """generate schema from a support module definition yaml"""
    clear_entity_model_ids()

    schema_path = tmp_path / "single.ibek.support.schema.json"
    yaml_path = samples / "support" / "motorSim.ibek.support.yaml"
    run_cli("ioc", "generate-schema", yaml_path, "--output", schema_path)

    expected = json.loads(
        (samples / "schemas" / "single.ibek.ioc.schema.json").read_text()
    )

    actual = json.loads((schema_path).read_text())
    assert expected == actual


def test_motor_sim_schema(tmp_path: Path, samples: Path):
    clear_entity_model_ids()
    """generate schema for a container with two support modules"""

    schema_combined = tmp_path / "motorSim.ibek.ioc.schema.json"
    yaml_path1 = samples / "support" / "asyn.ibek.support.yaml"
    yaml_path2 = samples / "support" / "motorSim.ibek.support.yaml"
    run_cli(
        "ioc",
        "generate-schema",
        "--no-ibek-defs",
        yaml_path1,
        yaml_path2,
        "--output",
        schema_combined,
    )

    expected = json.loads(
        (samples / "schemas" / "motorSim.ibek.ioc.schema.json").read_text()
    )

    actual = json.loads((schema_combined).read_text())
    assert expected == actual


def test_build_runtime_motorSim(mocker: MockerFixture, tmp_path: Path, samples: Path):
    """
    build an ioc runtime script from an IOC instance entity file
    and multiple support module definition files

    Also verifies database subst file generation for multiple
    entity instantiations.
    """
    clear_entity_model_ids()
    ioc_yaml = samples / "iocs" / "ibek-mo-ioc-01.yaml"
    support_yaml1 = samples / "support" / "asyn.ibek.support.yaml"
    support_yaml2 = samples / "support" / "motorSim.ibek.support.yaml"
    expected_outputs = samples / "outputs" / "motorSim"

    mocker.patch.object(GLOBALS, "RUNTIME_OUTPUT", tmp_path)
    mocker.patch.object(GLOBALS, "OPI_OUTPUT", tmp_path)

    os.environ["IOC"] = "/epics/ioc"
    os.environ["RUNTIME_DIR"] = "/epics/runtime"
    generate(ioc_yaml, [support_yaml1, support_yaml2])

    example_boot = (expected_outputs / "st.cmd").read_text()
    actual_boot = (tmp_path / "st.cmd").read_text()
    assert example_boot == actual_boot

    example_db = (expected_outputs / "ioc.subst").read_text()
    actual_db = (tmp_path / "ioc.subst").read_text()
    assert example_db == actual_db

    example_index = (expected_outputs / "index.bob").read_text()
    actual_index = (tmp_path / "index.bob").read_text()
    assert example_index == actual_index

    example_bob = (expected_outputs / "simple.pvi.bob").read_text()
    actual_bob = (tmp_path / "simple.pvi.bob").read_text()
    assert example_bob == actual_bob

    example_template = (expected_outputs / "simple.pvi.template").read_text()
    actual_template = (tmp_path / "simple.pvi.template").read_text()
    assert example_template == actual_template


def test_build_utils_features(mocker: MockerFixture, tmp_path: Path, samples: Path):
    """
    build an ioc runtime script to verify utils features
    """
    clear_entity_model_ids()
    ioc_yaml = samples / "iocs" / "utils.ibek.ioc.yaml"
    support_yaml = samples / "support" / "utils.ibek.support.yaml"

    mocker.patch.object(GLOBALS, "RUNTIME_OUTPUT", tmp_path)

    os.environ["IOC"] = "/epics/ioc"
    os.environ["RUNTIME_DIR"] = "/epics/runtime"
    run_cli("runtime", "generate", ioc_yaml, support_yaml)

    example_boot = (samples / "outputs" / "utils" / "st.cmd").read_text()
    actual_boot = (tmp_path / "st.cmd").read_text()
    assert example_boot == actual_boot

    example_db = (samples / "outputs" / "utils" / "ioc.subst").read_text()
    actual_db = (tmp_path / "ioc.subst").read_text()
    assert example_db == actual_db


def test_generate_links_ibek(samples: Path, mocker: MockerFixture):
    symlink_mock = mocker.patch("ibek.support_cmds.commands.symlink_files")

    generate_links(samples / "support")

    symlink_mock.assert_any_call(
        samples / "support", PVI_YAML_PATTERN, GLOBALS.PVI_DEFS
    )
    symlink_mock.assert_any_call(
        samples / "support", SUPPORT_YAML_PATTERN, GLOBALS.IBEK_DEFS
    )
