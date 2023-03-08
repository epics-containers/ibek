from pathlib import Path

from typer.testing import CliRunner

from ibek.ioc import clear_entity_classes

from .test_cli import run_cli

runner = CliRunner()


def test_example_ioc(tmp_path: Path, samples: Path):
    """
    build an ioc from yaml and verify the result

    includes use of the feature 'pre_ioc_init'
    """
    clear_entity_classes()

    tmp_path = Path("/tmp/ibek_test")
    tmp_path.mkdir(exist_ok=True)

    entity_file = samples / "config" / "test.ibek.ioc.yaml"
    definition_file = samples / "yaml" / "epics.ibek.support.yaml"
    definition_file2 = samples / "yaml" / "deviocstats.ibek.support.yaml"
    out_file = tmp_path / "new_dir" / "test.ioc.cmd"
    out_db = tmp_path / "new_dir" / "make_db.sh"

    run_cli(
        "build-startup",
        entity_file,
        definition_file,
        definition_file2,
        "--out",
        out_file,
        "--db-out",
        out_db,
    )

    example_boot = (samples / "boot_scripts" / "test.ioc.cmd").read_text()
    actual_boot = out_file.read_text()

    example_db = (samples / "boot_scripts" / "test.ioc.make_db.sh").read_text()
    actual_db = out_db.read_text()

    assert example_boot == actual_boot
    assert example_db == actual_db
