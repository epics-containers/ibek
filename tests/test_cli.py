import json
from gc import collect
from pathlib import Path

from typer.testing import CliRunner

from ibek import __version__
from ibek.__main__ import app
from ibek.support import Support

runner = CliRunner()

sample_schemas = Path(__file__).parent / "samples" / "schemas"
sample_yaml = Path(__file__).parent / "samples" / "yaml"


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout == __version__ + "\n"


def test_builder_schema(tmp_path: Path):
    schema_path = tmp_path / "schema.json"
    result = runner.invoke(app, ["ibek-schema", str(schema_path)])
    assert result.exit_code == 0
    expected = json.loads(open(sample_schemas / "ibek.schema.json").read())
    # Don't care if version number didn't update to match if the rest is the same
    # expected["title"] = mock.ANY

    actual = json.loads(open(schema_path).read())
    assert expected == actual


def test_pmac_schema(tmp_path: Path):
    # When we deserialize the same yaml twice as we do in the full test suite
    # we may get clashes in the namespace of generated EntityInstance classes
    # It causes errors like this:
    #   <Result ValueError("Types <class 'types.pmac.Geobrick'> and
    #     <class 'types.pmac.Geobrick'> share same reference 'pmac.Geobrick'")>

    Support.namespace.clear()
    collect()

    schema_path = tmp_path / "pmac.ibek.schema.json"
    yaml_path = sample_yaml / "pmac.ibek.yaml"
    result = runner.invoke(app, ["ioc-schema", str(yaml_path), str(schema_path)])
    assert result.exit_code == 0
    expected = json.loads(open(sample_schemas / "pmac.schema.json").read())

    actual = json.loads(open(schema_path).read())
    assert expected == actual
