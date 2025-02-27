"""
System tests for the ibek.repeat feature
"""

from pathlib import Path

from tests.test_cli import generic_generate


def test_repeat_example(tmp_epics_root: Path, tmp_path, samples):
    generic_generate(
        tmp_epics_root,
        samples,
        "repeat",
        ["epics", "asyn", "motorSim"],
    )


# def test_subentity_repeats(tmp_epics_root: Path, tmp_path, samples):
#     generic_generate(
#         tmp_epics_root,
#         samples,
#         "quadem",
#         ["ADCore", "quadem_repeat"],
#     )
