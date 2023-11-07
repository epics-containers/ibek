"""Unit tests for the support subcommand"""
from pathlib import Path

from ibek.support_cmds.files import symlink_files


def test_symlink_ibek(tmp_path: Path, samples: Path):
    symlink_files(samples / "yaml", "*.ibek.support.yaml", tmp_path)

    assert sorted([f.name for f in tmp_path.iterdir()]) == [
        "all.ibek.support.yaml",
        "bad_db.ibek.support.yaml",
        "objects.ibek.support.yaml",
        "utils.ibek.support.yaml",
    ]


def test_symlink_pvi(tmp_path: Path, samples: Path):
    symlink_files(samples / "yaml", "*.pvi.device.yaml", tmp_path)

    assert [f.name for f in tmp_path.iterdir()] == ["simple.pvi.device.yaml"]
