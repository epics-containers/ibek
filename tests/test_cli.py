"""
System tests that run the CLI commands and compare the output to expected
results.
"""
import json
import subprocess
import sys
from pathlib import Path

from ibek import __version__
from ibek.ioc import clear_entity_model_ids
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


def test_object_schema(tmp_path: Path, samples: Path):
    """generate schema from a simple support module definition yaml"""
    clear_entity_model_ids()

    schema_path = tmp_path / "objects.ibek.support.schema.json"
    yaml_path = samples / "yaml" / "objects.ibek.support.yaml"
    run_cli("ioc", "generate-schema", yaml_path, "--output", schema_path)

    expected = json.loads(
        (samples / "schemas" / "objects.ibek.ioc.schema.json").read_text()
    )

    actual = json.loads((schema_path).read_text())
    assert expected == actual


def test_ioc_schema(tmp_path: Path, samples: Path):
    clear_entity_model_ids()
    """generate schema for a container with two support modules"""

    schema_combined = tmp_path / "multiple.ibek.ioc.schema.json"
    yaml_path1 = samples / "yaml" / "objects.ibek.support.yaml"
    yaml_path2 = samples / "yaml" / "all.ibek.support.yaml"
    run_cli(
        "ioc", "generate-schema", yaml_path1, yaml_path2, "--output", schema_combined
    )

    expected = json.loads(
        (samples / "schemas" / "multiple.ibek.ioc.schema.json").read_text()
    )

    actual = json.loads((schema_combined).read_text())
    assert expected == actual


def test_build_startup_single(tmp_path: Path, samples: Path):
    """
    build an ioc startup script from an IOC instance entity file
    and a single support module definition file

    Also ensure output directory gets generated if it doesn't pre-exist
    """
    clear_entity_model_ids()
    ioc_yaml = samples / "yaml" / "objects.ibek.ioc.yaml"
    support_yaml = samples / "yaml" / "objects.ibek.support.yaml"
    out_file = tmp_path / "new_dir" / "st.cmd"
    out_db = tmp_path / "new_dir" / "objects.db.subst"

    run_cli(
        "startup",
        "generate",
        ioc_yaml,
        support_yaml,
        "--out",
        out_file,
        "--db-out",
        out_db,
    )

    example_boot = (samples / "outputs" / "objects.st.cmd").read_text()
    actual_boot = out_file.read_text()
    assert example_boot == actual_boot

    example_db = (samples / "outputs" / "objects.db.subst").read_text()
    actual_db = out_db.read_text()
    assert example_db == actual_db


def test_build_startup_multiple(tmp_path: Path, samples: Path):
    """
    build an ioc startup script from an IOC instance entity file
    and multiple support module definition files

    Also verifies database subst file generation for multiple
    entity instantiations.
    """
    clear_entity_model_ids()
    ioc_yaml = samples / "yaml" / "all.ibek.ioc.yaml"
    support_yaml = samples / "yaml" / "objects.ibek.support.yaml"
    support_yaml2 = samples / "yaml" / "all.ibek.support.yaml"
    out_file = tmp_path / "st.cmd"
    out_db = tmp_path / "all.db.subst"

    run_cli(
        "startup",
        "generate",
        ioc_yaml,
        support_yaml,
        support_yaml2,
        "--out",
        out_file,
        "--db-out",
        out_db,
    )

    example_boot = (samples / "outputs" / "all.st.cmd").read_text()
    actual_boot = out_file.read_text()
    assert example_boot == actual_boot

    example_db = (samples / "outputs" / "all.db.subst").read_text()
    actual_db = out_db.read_text()
    assert example_db == actual_db


def test_build_utils_features(tmp_path: Path, samples: Path):
    """
    build an ioc startup script to verify utils features
    """
    clear_entity_model_ids()
    ioc_yaml = samples / "yaml" / "utils.ibek.ioc.yaml"
    support_yaml = samples / "yaml" / "utils.ibek.support.yaml"
    out_file = tmp_path / "st.cmd"
    out_db = tmp_path / "db.subst"

    run_cli(
        "startup",
        "generate",
        ioc_yaml,
        support_yaml,
        "--out",
        out_file,
        "--db-out",
        out_db,
    )

    example_boot = (samples / "outputs" / "utils.st.cmd").read_text()
    actual_boot = out_file.read_text()
    assert example_boot == actual_boot

    example_db = (samples / "outputs" / "utils.db.subst").read_text()
    actual_db = out_db.read_text()
    assert example_db == actual_db
