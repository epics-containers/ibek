"""
System tests that run the CLI commands and compare the output to expected
results.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

import ibek.utils as utils
from ibek import __version__
from ibek.globals import GLOBALS
from ibek.runtime_cmds.commands import do_generate, find_pvi_device
from tests.conftest import run_cli

runner = CliRunner()


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
    with pytest.deprecated_call():
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
    with pytest.deprecated_call():
        generic_generate(
            tmp_epics_root,
            samples,
            "quadem",
            ["ADCore", "quadem"],
        )


def generic_generate(
    epics_root: Path, samples: Path, ioc_yaml_name: str, support_names: list[str]
):
    ioc_yaml = samples / "iocs" / f"{ioc_yaml_name}.ibek.ioc.yaml"
    support_yamls = [
        samples / "support" / f"{name}.ibek.support.yaml" for name in support_names
    ]
    expected_outputs = samples / "outputs" / ioc_yaml_name

    do_generate([ioc_yaml], support_yamls, epics_root / "runtime", pvi=True)

    outputs = list(expected_outputs.glob("*"))
    assert len(outputs) > 0, "No expected output files found"

    for output in outputs:
        actual = epics_root / "runtime" / output.name
        if not actual.exists():
            actual = epics_root / "opi" / output.name
        assert actual.exists(), f"Missing output file {actual}"
        assert output.read_text().strip() == actual.read_text().strip()


def test_find_pvi_device(tmp_epics_root: Path):
    """
    find_pvi_device resolves against PVI_DEFS, but a file of the same name
    dropped into the IOC instance config folder overrides it.
    """
    config_dir = GLOBALS.IOC_FOLDER / GLOBALS.CONFIG_DIR_NAME

    # with no override the file resolves relative to PVI_DEFS
    assert find_pvi_device("simple.pvi.device.yaml", config_dir) == (
        GLOBALS.PVI_DEFS / "simple.pvi.device.yaml"
    )

    # a relative sub-path with no override is preserved under PVI_DEFS
    assert find_pvi_device("sub/simple.pvi.device.yaml", config_dir) == (
        GLOBALS.PVI_DEFS / "sub" / "simple.pvi.device.yaml"
    )

    # dropping a file of the same name in the config folder overrides it,
    # matching on file name only
    override = config_dir / "simple.pvi.device.yaml"
    override.write_text("label: Overridden Device\n")
    assert find_pvi_device("simple.pvi.device.yaml", config_dir) == override
    assert find_pvi_device("sub/simple.pvi.device.yaml", config_dir) == override


def test_pvi_config_override(tmp_epics_root: Path, samples: Path):
    """
    A pvi device yaml dropped into the IOC instance config folder overrides the
    one shipped in PVI_DEFS by a support module.
    """
    config_dir = GLOBALS.IOC_FOLDER / GLOBALS.CONFIG_DIR_NAME
    (config_dir / "simple.pvi.device.yaml").write_text(
        "label: Overridden Device\n"
        "children:\n"
        "  - type: SignalR\n"
        "    name: SimplePV\n"
        "    read_pv: $(P)Simple\n"
        "    read_widget:\n"
        "      type: TextRead\n"
    )

    with pytest.deprecated_call():
        do_generate(
            [samples / "iocs" / "motorSim.ibek.ioc.yaml"],
            [
                samples / "support" / f"{name}.ibek.support.yaml"
                for name in ["motorSim", "asyn"]
            ],
            tmp_epics_root / "runtime",
            pvi=True,
        )

    bob = (GLOBALS.OPI_OUTPUT / "simple.pvi.bob").read_text()
    assert "Overridden Device" in bob
    assert "Simple Device" not in bob


def test_pvi_config_override_parent(tmp_epics_root: Path, samples: Path):
    """
    A pvi device yaml in the IOC instance config folder also overrides a device
    that is referenced as a *parent* of another device. Here the quadem IOC
    generates NDPluginStats, whose parent is NDPluginDriver; overriding
    NDPluginDriver in the config folder changes the generated NDPluginStats bob.
    """
    config_dir = GLOBALS.IOC_FOLDER / GLOBALS.CONFIG_DIR_NAME
    # an override parent device with a single, uniquely named signal
    (config_dir / "NDPluginDriver.pvi.device.yaml").write_text(
        "label: NDPluginDriver\n"
        "parent: asynNDArrayDriver\n"
        "children:\n"
        "  - type: SignalR\n"
        "    name: OverriddenParentSignal\n"
        "    read_pv: $(P)$(R)OverriddenParentSignal_RBV\n"
        "    read_widget:\n"
        "      type: TextRead\n"
    )

    with pytest.deprecated_call():
        do_generate(
            [samples / "iocs" / "quadem.ibek.ioc.yaml"],
            [
                samples / "support" / f"{name}.ibek.support.yaml"
                for name in ["ADCore", "quadem"]
            ],
            tmp_epics_root / "runtime",
            pvi=True,
        )

    bob = (GLOBALS.OPI_OUTPUT / "NDPluginStats.pvi.bob").read_text()
    # the overridden parent's signal is present...
    assert "OverriddenParentSignal" in bob
    # ...and signals only present in the original PVI_DEFS parent are gone
    assert "EnableCallbacks" not in bob


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


def test_dls8515(tmp_epics_root: Path, samples: Path):
    """
    Cut down copy of dlsPLC containing fast vacuum master and channel
    """
    with pytest.raises(ValueError) as ctx:
        generic_generate(
            tmp_epics_root,
            samples,
            "DLS8515",
            ["DLS8515", "ipac", "epics"],
        )

    assert "`ipac.Hy8002`.interrupt_vector" in str(ctx.value)
