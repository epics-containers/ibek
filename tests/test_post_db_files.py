"""
Tests for the IOC-level post_db_files list: database files from the instance
config folder that st.cmd loads after ioc.db and before iocInit.
"""

import json
from pathlib import Path

import pytest
import typer

from ibek.runtime_cmds.commands import do_generate
from ibek.utils import UTILS
from tests.conftest import run_cli

IOC_DB = "dbLoadRecords /epics/runtime/ioc.db\n"


def make_config(
    tmp_path: Path, samples: Path, post_db_files: list[str] | None
) -> Path:
    """An instance config folder holding the utils sample ioc.yaml"""
    config = tmp_path / "config"
    config.mkdir()
    ioc_yaml = (samples / "iocs" / "utils.ibek.ioc.yaml").read_text()
    if post_db_files is not None:
        ioc_yaml += f"\npost_db_files: {json.dumps(post_db_files)}\n"
    (config / "ioc.yaml").write_text(ioc_yaml)
    return config


def generate(epics_root: Path, samples: Path, instances: list[Path], config: Path):
    support = samples / "support" / "utils.ibek.support.yaml"
    # the utils sample's counters live in UTILS: start each render from zero
    UTILS.__reset__()
    do_generate(instances, [support], epics_root / "runtime", False, config)
    return (epics_root / "runtime" / "st.cmd").read_text()


@pytest.mark.parametrize("post_db_files", [None, []])
def test_empty_post_db_files_leaves_st_cmd_unchanged(
    tmp_epics_root: Path, samples: Path, tmp_path: Path, post_db_files
):
    config = make_config(tmp_path, samples, post_db_files)
    st_cmd = generate(tmp_epics_root, samples, [config / "ioc.yaml"], config)
    expected = (samples / "outputs" / "utils" / "st.cmd").read_text()
    assert st_cmd == expected


def test_post_db_files_load_in_order_between_ioc_db_and_iocinit(
    tmp_epics_root: Path, samples: Path, tmp_path: Path
):
    config = make_config(tmp_path, samples, ["records.db", "sub/more.db"])
    (config / "records.db").touch()
    (config / "sub").mkdir()
    (config / "sub" / "more.db").touch()

    st_cmd = generate(tmp_epics_root, samples, [config / "ioc.yaml"], config)

    assert (
        IOC_DB + "dbLoadRecords config/records.db\n"
        "dbLoadRecords config/sub/more.db\n"
        "iocInit\n"
    ) in st_cmd


@pytest.mark.parametrize("entry", ["missing.db", "sub", "/etc/hostname"])
def test_post_db_file_not_in_config_folder_is_an_error(
    tmp_epics_root: Path,
    samples: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
    entry: str,
):
    config = make_config(tmp_path, samples, ["records.db", entry])
    (config / "records.db").touch()
    (config / "sub").mkdir()

    with pytest.raises(typer.Exit):
        generate(tmp_epics_root, samples, [config / "ioc.yaml"], config)
    assert f"post_db_files entries are not files in {config}: {entry}" in (
        capsys.readouterr().err
    )
    assert not (tmp_epics_root / "runtime" / "st.cmd").exists()


def test_post_db_files_from_ioc_and_runtime_yaml_concatenate(
    tmp_epics_root: Path, samples: Path, tmp_path: Path
):
    config = make_config(tmp_path, samples, ["a.db"])
    (config / "runtime.yaml").write_text(
        "ioc_name: counter\n"
        "description: runtime entities\n"
        "entities: []\n"
        "post_db_files: [b.db, c.db]\n"
    )
    for name in "a.db", "b.db", "c.db":
        (config / name).touch()

    st_cmd = generate(
        tmp_epics_root,
        samples,
        [config / "ioc.yaml", config / "runtime.yaml"],
        config,
    )

    assert (
        IOC_DB + "dbLoadRecords config/a.db\n"
        "dbLoadRecords config/b.db\n"
        "dbLoadRecords config/c.db\n"
        "iocInit\n"
    ) in st_cmd


def test_schema_has_post_db_files(tmp_path: Path, samples: Path):
    schema_path = tmp_path / "utils.ibek.ioc.schema.json"
    run_cli(
        "ioc",
        "generate-schema",
        "--no-ibek-defs",
        samples / "support" / "utils.ibek.support.yaml",
        "--output",
        schema_path,
    )
    schema = json.loads(schema_path.read_text())
    field = schema["properties"]["post_db_files"]
    assert field["type"] == "array"
    assert field["items"] == {"type": "string"}
    assert field["default"] == []
    assert "post_db_files" not in schema.get("required", [])
