"""
Tests for the ibek runtime commands
"""

from ibek.runtime_cmds.autosave import AutosaveGenerator, link_req_files


def test_autosave_generator(samples, tmp_epics_root):
    """Test the autosave generator"""

    link_req_files()
    link_req_files()
    files = list((tmp_epics_root / "autosave").glob("*"))
    assert len(files) == 1

    autosave_gen = AutosaveGenerator(samples / "runtime" / "ioc.subst")
    assert (
        str(autosave_gen.subst_entries[0].template_file)
        == "$(IOCSTATS)/db/iocAdminSoft.db"
    )
