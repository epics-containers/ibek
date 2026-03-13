"""
Tests for the `ioc do-wait` CLI command.
"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from typer.testing import CliRunner

import ibek.ioc_cmds.commands as ioc_cmds_module
from ibek.__main__ import cli

runner = CliRunner()


@pytest.fixture()
def dowait_done_file(tmp_path: Path, mocker: MockerFixture) -> Path:
    """Redirect DOWAIT_DONE_FILE into tmp_path and return its path."""
    # Patch the DOWAIT_DONE_FILE constant in the ioc_cmds_module
    # to point to a temporary file path.
    done_file = tmp_path / "doWait_completed.txt"
    mocker.patch.object(ioc_cmds_module, "DOWAIT_DONE_FILE", done_file)
    return done_file


def test_do_wait_missing_file(tmp_path: Path, dowait_done_file: Path):
    """
    When the source YAML does not exist do_wait should skip silently, report
    the missing file, and still create the done file so that dependent
    processes are not blocked.
    """
    # Use a path that doesn't exist for the wait list source
    nonexistent = tmp_path / "nonexistent_wait_list.yaml"

    # Run do_wait with the nonexistent file
    result = runner.invoke(cli, ["ioc", "do-wait", "--source", str(nonexistent)])

    # The command should exit successfully with a warning about the missing file
    assert result.exit_code == 0
    assert "No wait list file found" in result.output
    assert dowait_done_file.exists()


def test_do_wait_unsupported_type(tmp_path: Path, dowait_done_file: Path):
    """
    An entry with an unrecognised type should be reported as a warning but
    do_wait should still exit successfully and create the done file.
    """
    # Create a wait list with an unsupported type
    wait_yaml = tmp_path / "wait_list.yaml"
    wait_yaml.write_text("- type: ibek.wait_usb\n  device: myDevice\n")

    # Run do_wait with the unsupported entry
    result = runner.invoke(cli, ["ioc", "do-wait", "--source", str(wait_yaml)])

    # The command should exit successfully with a warning about the unsupported type
    assert result.exit_code == 0
    assert "not supported" in result.output
    assert dowait_done_file.exists()


def test_do_wait_retries_on_transient_error(
    tmp_path: Path, dowait_done_file: Path, mocker: MockerFixture
):
    """
    Transient network errors (ECONNREFUSED / ENETUNREACH) are converted to
    TimeoutError by try_connect.  do_wait must keep retrying until the
    connection succeeds rather than aborting immediately.
    """
    # Create a wait list with one entry that will fail with transient errors before succeeding
    wait_yaml = tmp_path / "wait_list.yaml"
    wait_yaml.write_text(
        "- type: ibek.wait_ip\n"
        "  device: myDevice\n"
        "  address: '127.0.0.1:9999'\n"
        "  timeout: 10\n"
    )

    # Mock try_connect to fail with transient errors on the first two attempts, then succeed on the third attempt
    mock_try_connect = mocker.patch.object(ioc_cmds_module, "try_connect")
    mock_try_connect.side_effect = [
        TimeoutError("Connection refused"),
        TimeoutError("Network unreachable"),
        None,  # third attempt succeeds
    ]

    # Run do_wait command
    result = runner.invoke(cli, ["ioc", "do-wait", "--source", str(wait_yaml)])

    # Verify that do_wait retried after the transient errors and eventually succeeded
    assert result.exit_code == 0
    assert mock_try_connect.call_count == 3
    assert dowait_done_file.exists()
    assert "All 'wait' commands completed successfully." in result.output


def test_do_wait_timeout_expiry(
    tmp_path: Path, dowait_done_file: Path, mocker: MockerFixture
):
    """
    When every connection attempt fails and the overall timeout window
    elapses, do_wait should exit with a non-zero code and report the timeout.
    """
    # Create a wait list with one entry that will always fail with transient errors
    wait_yaml = tmp_path / "wait_list.yaml"
    wait_yaml.write_text(
        "- type: ibek.wait_ip\n"
        "  device: myDevice\n"
        "  address: '127.0.0.1:9999'\n"
        "  timeout: 0.1\n"  # short timeout so the test completes quickly
    )

    # Mock try_connect to always raise a transient error
    mocker.patch.object(
        ioc_cmds_module,
        "try_connect",
        side_effect=TimeoutError("Connection timed out"),
    )

    # Run do_wait command
    result = runner.invoke(cli, ["ioc", "do-wait", "--source", str(wait_yaml)])

    # The command should exit with a non-zero code and report the timeout
    assert result.exit_code == 1
    assert "timed out" in result.output
