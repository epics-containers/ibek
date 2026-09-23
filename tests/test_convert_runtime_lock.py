"""
Tests for the standalone ``scripts/convert-runtime-lock.py``.

The script is deliberately not part of the installed ``ibek`` package (see its
own docstring) so that it runs unmodified from a services repo with no ``ibek``
checkout. It is therefore loaded here by file path rather than imported as a
package module.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from ruamel.yaml import YAML

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "convert-runtime-lock.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("convert_runtime_lock", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load_script()


def write_lock(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def load_yaml(path: Path):
    return YAML(typ="safe").load(path)


def test_flat_lock_converted_to_wrapped(tmp_path: Path, script, capsys):
    lock = write_lock(
        tmp_path / "runtime-lock.yaml",
        "mydevice@1.0.0:\n"
        "  version: 1.0.0\n"
        "  source: somewhere\n"
        "  files:\n"
        "    mydevice.proto: sha256:deadbeef\n",
    )

    rc = script.main([str(lock)])

    assert rc == 0
    assert "converted 1 pattern(s): mydevice@1.0.0" in capsys.readouterr().out
    assert load_yaml(lock) == {
        "version": 1,
        "patterns": {
            "mydevice@1.0.0": {
                "version": "1.0.0",
                "source": "somewhere",
                "files": {"config/mydevice.proto": "sha256:deadbeef"},
            }
        },
    }


def test_idempotent_on_already_wrapped_lock(tmp_path: Path, script, capsys):
    text = (
        "version: 1\n"
        "patterns:\n"
        "  mydevice:\n"
        "    version: 1.0.0\n"
        "    source: somewhere\n"
        "    files:\n"
        "      config/mydevice.proto: sha256:deadbeef\n"
    )
    lock = write_lock(tmp_path / "runtime-lock.yaml", text)

    rc = script.main([str(lock)])

    assert rc == 0
    assert "already in the format ibek reads; nothing to do" in capsys.readouterr().out
    assert lock.read_text() == text  # byte-identical: untouched


def test_empty_lock_converts_to_no_patterns(tmp_path: Path, script, capsys):
    lock = write_lock(tmp_path / "runtime-lock.yaml", "")

    rc = script.main([str(lock)])

    assert rc == 0
    assert "converted 0 pattern(s):" in capsys.readouterr().out
    assert load_yaml(lock) == {"version": 1, "patterns": {}}


def test_multi_pattern_lock_converted_and_sorted(tmp_path: Path, script, capsys):
    lock = write_lock(
        tmp_path / "runtime-lock.yaml",
        "zeta@1.0.0:\n"
        "  files:\n"
        "    zeta.proto: sha256:zzz\n"
        "alpha@1.0.0:\n"
        "  files:\n"
        "    alpha.proto: sha256:aaa\n",
    )

    rc = script.main([str(lock)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "converted 2 pattern(s): alpha@1.0.0, zeta@1.0.0" in out
    data = load_yaml(lock)
    assert list(data["patterns"]) == ["alpha@1.0.0", "zeta@1.0.0"]
    assert data["patterns"]["alpha@1.0.0"]["files"] == {
        "config/alpha.proto": "sha256:aaa"
    }
    assert data["patterns"]["zeta@1.0.0"]["files"] == {
        "config/zeta.proto": "sha256:zzz"
    }


def test_key_already_starting_with_config_is_still_prefixed(tmp_path: Path, script):
    """A flat lock's keys are always ``config/``-relative, even one that
    already spells ``config/`` — e.g. a pattern that vendors its own nested
    ``config/`` folder — so the prefix must not be skipped for it."""
    lock = write_lock(
        tmp_path / "runtime-lock.yaml",
        "mydevice@1.0.0:\n  files:\n    config/nested.proto: sha256:deadbeef\n",
    )

    rc = script.main([str(lock)])

    assert rc == 0
    data = load_yaml(lock)
    assert set(data["patterns"]["mydevice@1.0.0"]["files"]) == {
        "config/config/nested.proto"
    }


def test_missing_file_exits_1(tmp_path: Path, script, capsys):
    rc = script.main([str(tmp_path / "missing.yaml")])

    assert rc == 1
    assert "no such file" in capsys.readouterr().err


def test_invalid_yaml_exits_1(tmp_path: Path, script, capsys):
    lock = write_lock(tmp_path / "runtime-lock.yaml", "mydevice: [unterminated\n")

    rc = script.main([str(lock)])

    assert rc == 1
    assert "invalid YAML" in capsys.readouterr().err


def test_non_mapping_top_level_exits_1(tmp_path: Path, script, capsys):
    lock = write_lock(tmp_path / "runtime-lock.yaml", "- not\n- a mapping\n")

    rc = script.main([str(lock)])

    assert rc == 1
    assert "expected a mapping" in capsys.readouterr().err


def test_not_a_pattern_lock_exits_1(tmp_path: Path, script, capsys):
    lock = write_lock(tmp_path / "runtime-lock.yaml", "foo: 3\n")

    rc = script.main([str(lock)])

    assert rc == 1
    assert "not a pattern lock" in capsys.readouterr().err


def test_no_args_exits_2(script, capsys):
    rc = script.main([])

    assert rc == 2
    assert "usage:" in capsys.readouterr().err
