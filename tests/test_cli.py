from typer.testing import CliRunner

from ibek import __version__
from ibek.__main__ import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout == __version__ + "\n"
