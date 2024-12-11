"""
Tests for the ibek runtime commands
"""

from ibek.runtime_cmds.autosave import AutosaveGenerator


def test_autosave_generator(samples):
    """Test the autosave generator"""
    autosave_gen = AutosaveGenerator(samples / "runtime" / "ioc.subst")
    assert (
        autosave_gen.subst_entries[0].template_file == "$(IOCSTATS)/db/iocAdminSoft.db"
    )
