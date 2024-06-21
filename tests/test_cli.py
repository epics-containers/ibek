"""
System tests that run the CLI commands and compare the output to expected
results.
"""

import json
import subprocess
import sys
from pathlib import Path

from pytest_mock import MockerFixture

import ibek.utils as utils
from ibek import __version__
from ibek.globals import (
    GLOBALS,
    PVI_YAML_PATTERN,
    SUPPORT_YAML_PATTERN,
)
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

    schema_path = tmp_path / "single.ibek.support.schema.json"
    yaml_path = samples / "support" / "motorSim.ibek.support.yaml"
    run_cli(
        "ioc", "generate-schema", "--no-ibek-defs", yaml_path, "--output", schema_path
    )

    expected = json.loads(
        (samples / "schemas" / "single.ibek.ioc.schema.json").read_text()
    )

    actual = json.loads((schema_path).read_text())
    assert expected == actual


def test_motor_sim_schema(tmp_path: Path, samples: Path):
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


def test_build_runtime_motorSim(tmp_epics_root: Path, samples: Path):
    """
    build an ioc runtime script from an IOC instance entity file
    and multiple support module definition files

    Also verifies database subst file generation for multiple
    entity instantiations.
    """

    generic_generate(
        tmp_epics_root,
        samples,
        "motorSim",
        ["motorSim", "asyn"],
    )


def test_build_utils_features(tmp_epics_root: Path, samples: Path):
    """
    build an ioc runtime script to verify utils features
    """
    generic_generate(
        tmp_epics_root,
        samples,
        "utils",
        ["utils"],
    )


def test_generate_links_ibek(samples: Path, mocker: MockerFixture):
    symlink_mock = mocker.patch("ibek.support_cmds.commands.symlink_files")

    generate_links(samples / "support")

    symlink_mock.assert_any_call(
        samples / "support", PVI_YAML_PATTERN, GLOBALS.PVI_DEFS
    )
    symlink_mock.assert_any_call(
        samples / "support", SUPPORT_YAML_PATTERN, GLOBALS.IBEK_DEFS
    )


def test_ipac(tmp_epics_root: Path, samples: Path):
    """
    Tests that an id argument can include another argument in its default value
    """

    # reset the InterruptVector counter to its initial state (if already used)
    if "InterruptVector" in utils.UTILS.variables:
        utils.UTILS.variables["InterruptVector"] = 191

    generic_generate(
        tmp_epics_root,
        samples,
        "ipac-test",
        ["ipac", "epics"],
    )


def test_gauges(tmp_epics_root: Path, samples: Path):
    """
    Tests that an id argument can include another argument in its default value
    """
    generic_generate(
        tmp_epics_root,
        samples,
        "gauges",
        ["asyn", "gauges"],
    )


def test_quadem(tmp_epics_root: Path, samples: Path):
    """
    Tests the use of CollectionDefinitions in an IOC instance
    this example uses the tetramm beam position monitor module
    """
    generic_generate(
        tmp_epics_root,
        samples,
        "quadem",
        ["ADCore", "quadem"],
    )


def generic_generate(
    epics_root: Path, samples: Path, ioc_name: str, support_names: list[str]
):
    ioc_yaml = samples / "iocs" / f"{ioc_name}.ibek.ioc.yaml"
    support_yamls = [
        samples / "support" / f"{name}.ibek.support.yaml" for name in support_names
    ]
    expected_outputs = samples / "outputs" / ioc_name

    generate(ioc_yaml, support_yamls)

    for output in expected_outputs.glob("*"):
        actual = epics_root / "runtime" / output.name
        if not actual.exists():
            actual = epics_root / "opi" / output.name
        assert actual.exists(), "Missing output file"
        assert output.read_text() == actual.read_text()


def test_andreas_motors(tmp_epics_root: Path, samples: Path):
    """
    Motor and axis example
    """
    generic_generate(
        tmp_epics_root,
        samples,
        "technosoft",
        ["asyn", "technosoft"],
    )


def test_list(tmp_epics_root: Path, samples: Path):
    """
    Motor and axis example
    """
    generic_generate(
        tmp_epics_root,
        samples,
        "listarg",
        ["listarg"],
    )


def test_fast_vacuum(tmp_epics_root: Path, samples: Path):
    """
    Cut down copy of dlsPLC containing fast vacuum master and channel
    """
    generic_generate(
        tmp_epics_root,
        samples,
        "fastVacuum",
        ["fastVacuum"],
    )


def test_dls_plc(tmp_epics_root: Path, samples: Path):
    """
    Cut down copy of dlsPLC containing fast vacuum master and channel
    """
    generic_generate(
        tmp_epics_root,
        samples,
        "dlsPLC",
        ["dlsPLC", "asyn"],
    )
