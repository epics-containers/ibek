import json
from pathlib import Path

from apischema.json_schema import deserialization_schema
from typer.testing import CliRunner

from ibek import __version__
from ibek.__main__ import app
from ibek.dataclass_from_yaml import yaml_to_dataclass

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

    schema_path = tmp_path / "pmac.ibek.schema.json"
    yaml_path = sample_yaml / "pmac.ibek.yaml"
    result = runner.invoke(app, ["ioc-schema", str(yaml_path), str(schema_path)])
    assert result.exit_code == 0
    expected = json.loads(open(sample_schemas / "pmac.schema.json").read())

    actual = json.loads(open(schema_path).read())
    assert expected == actual


def test_may_fail(tmp_path: Path):
    # When we deserialize the same yaml twice as we do in the full test suite
    # we may get clashes in the namespace of generated EntityInstance classes
    # It causes errors like this:
    #   <Result ValueError("Types <class 'types.pmac.Geobrick'> and
    #     <class 'types.pmac.Geobrick'> share same reference 'pmac.Geobrick'")>
    # I was getting this error in the above test test_pmac_schema when I ran
    # the test suite but not when I ran it standalone.
    #
    # This test is a standalone attempt to reproduce the error but while
    # working on it the error has gone away and I don't understand whats up.
    description = sample_yaml / "pmac.ibek.yaml"

    support1 = yaml_to_dataclass(str(description))
    ioc_class1 = support1.get_module_dataclass()
    schema1 = json.dumps(deserialization_schema(ioc_class1), indent=2)
    with open(tmp_path / "schema1", "w") as f:
        f.write(schema1)

    ioc_class2 = yaml_to_dataclass(str(description)).get_module_dataclass()
    schema2 = json.dumps(deserialization_schema(ioc_class2), indent=2)
    with open(tmp_path / "schema2", "w") as f:
        f.write(schema2)
