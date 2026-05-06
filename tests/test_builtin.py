"""
System tests for the ibek builtin commands
"""

from pathlib import Path

import pytest

from tests.test_cli import generic_generate

# Note that the tests will fail unless the './generate_samples.sh' script has been run first
# to generate the expected test output in the './samples/outputs/wait' directory.


def test_wait_example(tmp_epics_root: Path, samples):
    with pytest.deprecated_call():
        generic_generate(
            tmp_epics_root,
            samples,
            "wait",
            ["epics", "asyn", "motorSim"],
        )
