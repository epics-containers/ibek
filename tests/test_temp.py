from pathlib import Path

from typer.testing import CliRunner

from ibek.__main__ import cli
from ibek.ioc import clear_entity_classes

runner = CliRunner()


def run_cli(*args):
    result = runner.invoke(cli, [str(x) for x in args])
    if result.exception:
        raise result.exception
    assert result.exit_code == 0, result


"""
A test for debugging the creation of startup scripts
remove xx to run this in debug mode.
"""


def xxtest_build_startup_p45(tmp_path: Path, samples: Path):
    """
    build an ioc startup script from an IOC instance entity file
    and multiple support module definition files
    """
    root = Path("/workspace/bl45p")

    clear_entity_classes()
    entity_file = root / "bl45p-mo-ioc-99.yaml"
    definitions = Path.glob(root / "ibek", "*.ibek.defs.yaml")
    out_file = root / "iocs/bl45p-mo-ioc-99/config/ioc.boot"

    run_cli("build-startup", entity_file, *definitions, "--out", out_file)
