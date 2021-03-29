import json
from pathlib import Path

from typer.testing import CliRunner

from ibek import __version__
from ibek.__main__ import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout == __version__ + "\n"


def test_builder_schema(tmp_path: Path):
    schema_path = tmp_path / "schema.json"
    result = runner.invoke(app, ["builder-schema", str(schema_path)])
    assert result.exit_code == 0
    expected = json.loads(open(Path(__file__).parent / "builder-schema.json").read())
    # Don't care if version number didn't update to match if the rest is the same
    # expected["title"] = mock.ANY
    actual = json.loads(open(schema_path).read())
    assert expected == actual
