import json
import subprocess
import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from ibek import __version__
from ibek.__main__ import cli
from ibek.ioc import clear_entity_model_ids, make_entity_models, make_ioc_model
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


def test_pmac_schema(tmp_path: Path, samples: Path, ibek_defs: Path):
    """generate schema from the pmac support module definition yaml"""
    clear_entity_model_ids()

    schema_path = tmp_path / "pmac.ibek.entities.schema.json"
    yaml_path = ibek_defs / "pmac" / "pmac.ibek.support.yaml"
    run_cli("ioc-schema", yaml_path, schema_path)

    expected = json.loads(
        (samples / "schemas" / "pmac.ibek.entities.schema.json").read_text()
    )

    actual = json.loads((schema_path).read_text())
    assert expected == actual


def test_asyn_schema(tmp_path: Path, samples: Path, ibek_defs: Path):
    """generate schema from the asyn support module definition yaml"""
    clear_entity_model_ids()

    schema_path = tmp_path / "asyn.ibek.entities.schema.json"
    yaml_path = ibek_defs / "asyn" / "asyn.ibek.support.yaml"
    run_cli("ioc-schema", yaml_path, schema_path)

    expected = json.loads(
        (samples / "schemas" / "asyn.ibek.entities.schema.json").read_text()
    )

    actual = json.loads((schema_path).read_text())
    assert expected == actual


def test_container_schema(tmp_path: Path, samples: Path, ibek_defs: Path):
    clear_entity_model_ids()
    """generate schema for a container with two support modules"""

    schema_combined = tmp_path / "container.ibek.entities.schema.json"
    yaml_path1 = ibek_defs / "asyn" / "asyn.ibek.support.yaml"
    yaml_path2 = ibek_defs / "pmac" / "pmac.ibek.support.yaml"
    run_cli("ioc-schema", yaml_path1, yaml_path2, schema_combined)

    expected = json.loads(
        (samples / "schemas" / "container.ibek.entities.schema.json").read_text()
    )

    actual = json.loads((schema_combined).read_text())
    assert expected == actual


def test_build_startup_output_path(tmp_path: Path, samples: Path, ibek_defs: Path):
    """
    build an ioc startup script and ensure output directory gets generated
    if it doesn't pre-exist
    """
    clear_entity_model_ids()
    entity_file = samples / "yaml" / "bl45p-mo-ioc-02.ibek.ioc.yaml"
    definition_file = ibek_defs / "pmac" / "pmac.ibek.support.yaml"
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


def test_build_startup_single(tmp_path: Path, samples: Path, ibek_defs: Path):
    """
    build an ioc startup script from an IOC instance entity file
    and a single support module definition file
    """
    clear_entity_model_ids()
    entity_file = samples / "yaml" / "bl45p-mo-ioc-02.ibek.ioc.yaml"
    definition_file = ibek_defs / "pmac" / "pmac.ibek.support.yaml"
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


def test_build_startup_multiple(tmp_path: Path, samples: Path, ibek_defs: Path):
    """
    build an ioc startup script from an IOC instance entity file
    and multiple support module definition files
    """
    clear_entity_model_ids()
    entity_file = samples / "yaml" / "bl45p-mo-ioc-03.ibek.ioc.yaml"
    definition_file1 = ibek_defs / "asyn" / "asyn.ibek.support.yaml"
    definition_file2 = ibek_defs / "pmac" / "pmac.ibek.support.yaml"
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


def test_build_startup_env_vars_and_post_ioc_init(
    tmp_path: Path, samples: Path, ibek_defs: Path
):
    """
    build an ioc startup script from an IOC instance entity file, multiple
    support module definition files which include environment variables and
    post iocInit() entries
    """
    clear_entity_model_ids()
    entity_file = samples / "yaml" / "bl45p-mo-ioc-04.ibek.ioc.yaml"
    definition_file1 = ibek_defs / "_global" / "epics.ibek.support.yaml"
    definition_file2 = ibek_defs / "pmac" / "pmac.ibek.support.yaml"
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


def test_loading_module_twice(tmp_path: Path, samples: Path, ibek_defs: Path):
    """
    Now that we use pydantic it is OK to create the same entity twice

    Verify this.
    """

    definition_file = samples / "pydantic" / "test.ibek.support.yaml"
    instance_file = samples / "pydantic" / "test.ibek.ioc.yaml"

    support = Support(**YAML(typ="safe").load(definition_file))
    entities1 = make_entity_models(support)
    entities2 = make_entity_models(support)

    generic_ioc1 = make_ioc_model(entities1)
    generic_ioc2 = make_ioc_model(entities2)

    instance = YAML(typ="safe").load(instance_file)
    ioc1 = generic_ioc1(**instance)
    ioc2 = generic_ioc2(**instance)

    assert ioc1.model_dump() == ioc2.model_dump()


def test_bad_counter(tmp_path: Path, samples: Path):
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
