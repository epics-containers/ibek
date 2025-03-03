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


def test_subentity_repeats(tmp_epics_root: Path, tmp_path, samples):
    generic_generate(
        tmp_epics_root,
        samples,
        "quadem",
        ["ADCore", "quadem_repeat"],
    )

    # make sure that quadem_repeat and quadem are identical
    files = (samples / "outputs").glob("quadem_repeat/*")
    if len(list(files)) == 0:
        raise AssertionError("No files found in quadem_repeat")

    for f in files:
        assert (samples / "outputs" / "quadem" / f.name).read_text() == f.read_text()


def test_subentity_repeats_with_substitutions(tmp_epics_root: Path, tmp_path, samples):
    generic_generate(
        tmp_epics_root,
        samples,
        "subentity_test",
        ["subentity_test", "epics"],
    )
