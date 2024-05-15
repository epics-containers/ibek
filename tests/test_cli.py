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
    ioc_yaml = samples / "iocs" / "ibek-mo-ioc-01.yaml"
    support_yaml1 = samples / "support" / "asyn.ibek.support.yaml"
    support_yaml2 = samples / "support" / "motorSim.ibek.support.yaml"
    expected_outputs = samples / "outputs" / "motorSim"

    generate(ioc_yaml, [support_yaml1, support_yaml2])

    example_boot = (expected_outputs / "st.cmd").read_text()
    actual_boot = (tmp_epics_root / "runtime" / "st.cmd").read_text()
    assert example_boot == actual_boot

    example_db = (expected_outputs / "ioc.subst").read_text()
    actual_db = (tmp_epics_root / "runtime" / "ioc.subst").read_text()
    assert example_db == actual_db

    example_index = (expected_outputs / "index.bob").read_text()
    actual_index = (tmp_epics_root / "opi" / "index.bob").read_text()
    assert example_index == actual_index

    example_bob = (expected_outputs / "simple.pvi.bob").read_text()
    actual_bob = (tmp_epics_root / "opi" / "simple.pvi.bob").read_text()
    assert example_bob == actual_bob

    example_template = (expected_outputs / "simple.pvi.template").read_text()
    actual_template = (tmp_epics_root / "runtime" / "simple.pvi.template").read_text()
    assert example_template == actual_template


def test_build_utils_features(tmp_epics_root: Path, samples: Path):
    """
    build an ioc runtime script to verify utils features
    """
    ioc_yaml = samples / "iocs" / "utils.ibek.ioc.yaml"
    support_yaml = samples / "support" / "utils.ibek.support.yaml"

    run_cli("runtime", "generate", ioc_yaml, support_yaml)

    example_boot = (samples / "outputs" / "utils" / "st.cmd").read_text()
    actual_boot = (tmp_epics_root / "runtime" / "st.cmd").read_text()
    assert example_boot == actual_boot

    example_db = (samples / "outputs" / "utils" / "ioc.subst").read_text()
    actual_db = (tmp_epics_root / "runtime" / "ioc.subst").read_text()
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


def test_ipac(tmp_epics_root: Path, samples: Path):
    """
    Tests that an id argument can include another argument in its default value
    """

    ioc_yaml = samples / "iocs" / "ipac-test.yaml"
    support_yaml1 = samples / "support" / "ipac.ibek.support.yaml"
    support_yaml2 = samples / "support" / "epics.ibek.support.yaml"
    expected_outputs = samples / "outputs" / "ipac"

    # reset the InterruptVector counter to its initial state (if already used)
    if "InterruptVector" in utils.UTILS.counters:
        utils.UTILS.counters["InterruptVector"].current = 192

    generate(ioc_yaml, [support_yaml1, support_yaml2])

    example_boot = (expected_outputs / "st.cmd").read_text()
    actual_boot = (tmp_epics_root / "runtime" / "st.cmd").read_text()
    assert example_boot == actual_boot


def test_gauges(tmp_epics_root: Path, samples: Path):
    """
    Tests that an id argument can include another argument in its default value
    """
    ioc_yaml = samples / "iocs" / "gauges.ibek.ioc.yaml"
    support_yaml1 = samples / "support" / "asyn.ibek.support.yaml"
    support_yaml2 = samples / "support" / "gauges.ibek.support.yaml"
    expected_outputs = samples / "outputs" / "gauges"

    generate(ioc_yaml, [support_yaml1, support_yaml2])

    example_boot = (expected_outputs / "st.cmd").read_text()
    actual_boot = (tmp_epics_root / "runtime" / "st.cmd").read_text()
    assert example_boot == actual_boot


def test_quadem(tmp_epics_root: Path, samples: Path):
    """
    Tests the use of CollectionDefinitions in an IOC instance
    this example uses the tetramm beam position monitor module
    """
    ioc_yaml = samples / "iocs" / "quadem.ibek.ioc.yaml"
    support_yaml1 = samples / "support" / "ADCore.ibek.support.yaml"
    support_yaml2 = samples / "support" / "quadem.ibek.support.yaml"
    expected_outputs = samples / "outputs" / "quadem"

    generate(ioc_yaml, [support_yaml1, support_yaml2])

    example_boot = (expected_outputs / "st.cmd").read_text()
    actual_boot = (tmp_epics_root / "runtime" / "st.cmd").read_text()
    assert example_boot == actual_boot

    example_db = (samples / "outputs" / "quadem" / "ioc.subst").read_text()
    actual_db = (tmp_epics_root / "runtime" / "ioc.subst").read_text()
    assert example_db == actual_db


def generic_generate(
    epics_root: Path, samples: Path, ioc_name: str, support_names: list[str]
):
    ioc_yaml = samples / "iocs" / f"{ioc_name}.ibek.ioc.yaml"
    support_yamls = [
        samples / "support" / f"{name}.ibek.support.yaml" for name in support_names
    ]
    expected_outputs = samples / "outputs" / ioc_name

    generate(ioc_yaml, support_yamls)

    example_boot = (expected_outputs / "st.cmd").read_text()
    actual_boot = (epics_root / "runtime" / "st.cmd").read_text()
    assert example_boot == actual_boot

    example_db = (expected_outputs / "ioc.subst").read_text()
    actual_db = (epics_root / "runtime" / "ioc.subst").read_text()
    assert example_db == actual_db


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
