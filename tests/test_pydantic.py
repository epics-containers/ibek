"""
Test the pydantic models for the ibek

ibek.defs.schema.json + test.ibek.support.yaml -> test.ibek.ioc.schema.json
test.ibek.ioc.schema.json + test.ibek.ioc.yaml -> startup script
"""
import json
from pathlib import Path

from typer.testing import CliRunner

from ibek.__main__ import cli

runner = CliRunner()


def run_cli(*args):
    result = runner.invoke(cli, [str(x) for x in args])
    if result.exception:
        raise result.exception
    assert result.exit_code == 0, result


def test_ioc_schema(tmp_path: Path, samples: Path):
    """generate the global ibek schema"""

    ibek_schema_path = tmp_path / "ibek.schema.json"
    run_cli("ibek-schema", ibek_schema_path)
    expected = json.loads((samples / "schemas" / "ibek.defs.schema.json").read_text())

    actual = json.loads(ibek_schema_path.read_text())
    assert expected == actual

    pydantic_sample_path = samples / "pydantic"
    ioc_schema_name = "test.ibek.ioc.schema.json"
    ibek_schema_path = tmp_path / ioc_schema_name
    support_yaml_path = pydantic_sample_path / "test.ibek.support.yaml"

    # generate schema from test.ibek.support.yaml
    run_cli("ioc-schema", support_yaml_path, ibek_schema_path)

    expected = json.loads((pydantic_sample_path / ioc_schema_name).read_text())

    actual = json.loads(ibek_schema_path.read_text())
    assert expected == actual


def test_ioc_build(tmp_path: Path, samples: Path):
    """generate the global ibek schema"""

    pydantic_sample_path = samples / "pydantic"
    support_yaml_path = pydantic_sample_path / "test.ibek.support.yaml"

    # generate startup script and from test.ibek.ioc.yaml
    ioc_yaml_path = pydantic_sample_path / "test.ibek.ioc.yaml"
    out_file = tmp_path / "st.cmd"
    out_db = tmp_path / "make_db.sh"

    run_cli(
        "build-startup",
        ioc_yaml_path,
        support_yaml_path,
        "--out",
        out_file,
        "--db-out",
        out_db,
    )

    example_boot = (pydantic_sample_path / "st.cmd").read_text()
    actual_boot = out_file.read_text()

    assert example_boot == actual_boot
