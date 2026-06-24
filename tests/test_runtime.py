"""
Tests for the ibek runtime commands
"""

from ibek.globals import GLOBALS
from ibek.runtime_cmds.autosave import AutosaveGenerator, link_req_files
from ibek.runtime_cmds.commands import place_runtime_files


def test_place_runtime_files(tmp_epics_root):
    """Runtime artifacts in config/ are placed into their boot locations."""
    config_dir = GLOBALS.IOC_FOLDER / GLOBALS.CONFIG_DIR_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "device.proto").write_text("Terminator = CR;\n")
    (config_dir / "extra.db").write_text("record(ai, x) {}\n")
    (config_dir / "ioc.yaml").write_text("ioc_name: test\n")  # not placed

    place_runtime_files(config_dir)

    assert (GLOBALS.RUNTIME_PROTOCOL / "device.proto").exists()
    assert (GLOBALS.RUNTIME_DB / "extra.db").exists()
    assert not (GLOBALS.RUNTIME_PROTOCOL / "ioc.yaml").exists()


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
