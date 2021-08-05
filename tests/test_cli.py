import json
from pathlib import Path

from apischema.json_schema import deserialization_schema
from typer.testing import CliRunner

from ibek import __version__
from ibek.__main__ import app
from ibek.generator import from_yaml

runner = CliRunner()

sample_schemas = Path(__file__).parent / "samples" / "schemas"
sample_yaml = Path(__file__).parent / "samples" / "yaml"
sample_helm = Path(__file__).parent / "samples" / "helm"


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


def test_build_ioc(tmp_path: Path):
    description = sample_yaml / "pmac.ibek.yaml"
    definition = sample_yaml / "bl45p-mo-ioc-02.pmac.yaml"

    result = runner.invoke(
        app, ["build-ioc", str(description), str(definition), str(tmp_path)]
    )
    assert result.exit_code == 0

    example_boot = (sample_helm / "ioc.boot").read_text()
    actual_file = tmp_path / "bl45p-mo-ioc-02" / "config" / "ioc.boot"
    actual_boot = actual_file.read_text()

    assert example_boot == actual_boot

    # TODO check chart and values yaml files too


def test_may_fail(tmp_path: Path):
    # When we deserialize the same yaml twice as we do in the full test suite
    # we may get clashes in the namespace of generated EntityInstance classes.
    #
    # I have seen errors like this:
    #   <Result ValueError("Types <class 'types.pmac.Geobrick'> and
    #     <class 'types.pmac.Geobrick'> share same reference 'pmac.Geobrick'")>
    # I was getting this error in the above test test_pmac_schema when I ran
    # the test suite but not when I ran it standalone.
    #
    # This test is a standalone attempt to reproduce the error but while
    # working on it the error has gone away and I don't understand whats up.
    #
    # I believe that this is the issue that Richard originally solved by
    # defining the EntityInstance base class in the scope of Support.
    # (I gave it global scope because I want to)
    definition_file = sample_yaml / "pmac.ibek.yaml"

    ioc_class1 = from_yaml(definition_file)

    schema1 = json.dumps(deserialization_schema(ioc_class1), indent=2)
    with open(tmp_path / "schema1", "w") as f:
        f.write(schema1)

    ioc_class2 = from_yaml(definition_file)
    schema2 = json.dumps(deserialization_schema(ioc_class2), indent=2)
    with open(tmp_path / "schema2", "w") as f:
        f.write(schema2)
