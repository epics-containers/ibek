"""Unit tests for the support subcommand"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from ibek.globals import GLOBALS
from ibek.support_cmds.checks import check_deps
from ibek.support_cmds.files import symlink_files


def test_symlink_ibek(tmp_path: Path, samples: Path):
    symlink_files(samples / "support", "*.ibek.support.yaml", tmp_path)

    assert sorted([f.name for f in tmp_path.iterdir()]) == [
        "ADCore.ibek.support.yaml",
        "asyn.ibek.support.yaml",
        "bad_db.ibek.support.yaml",
        "epics.ibek.support.yaml",
        "gauges.ibek.support.yaml",
        "ipac.ibek.support.yaml",
        "motorSim.ibek.support.yaml",
        "quadem.ibek.support.yaml",
        "utils.ibek.support.yaml",
    ]


def test_symlink_pvi(tmp_path: Path, samples: Path):
    symlink_files(samples / "support", "*.pvi.device.yaml", tmp_path)

    assert [f.name for f in tmp_path.iterdir()] == ["simple.pvi.device.yaml"]


@pytest.mark.skip("awaiting fix to the GLOBALS and mock patching issue")
def test_check_dependencies(mocker: MockerFixture, samples: Path):
    mocker.patch.object(GLOBALS, "SUPPORT", samples / "epics", "support")
    # Check Passes vs test data
    check_deps(["ADSimDetector"])

    # Check fails
    with pytest.raises(Exception):
        check_deps(["FakeDetector"])
