from pathlib import Path

from typer.testing import CliRunner

from ibek.ioc import clear_entity_model_ids
from ibek.utils import UTILS

from .test_cli import run_cli

runner = CliRunner()


def test_example_ioc(tmp_path: Path, samples: Path, ibek_defs: Path):
    """
    build an ioc from yaml and verify the result

    NOTE: the system test in tests/sys-test.sh uses the same example-ibek-config
    but instead of verifying the output, it runs the ioc in a container and \
    verifies that it starts up correctly.
    """
    clear_entity_model_ids()
    UTILS.__reset__()

    tmp_path = Path("/tmp/ibek_test")
    tmp_path.mkdir(exist_ok=True)

    entity_file = samples / "example-ibek-config" / "ioc.yaml"
    definition_file = ibek_defs / "_global" / "epics.ibek.support.yaml"
    definition_file2 = ibek_defs / "_global" / "devIocStats.ibek.support.yaml"
    out_file = tmp_path / "new_dir" / "test.ioc.cmd"
    out_db = tmp_path / "new_dir" / "make_db.sh"

    run_cli(
        "build-startup",
        entity_file,
        definition_file,
        definition_file2,
        "--out",
        out_file,
        "--db-out",
        out_db,
    )

    example_boot = (samples / "boot_scripts" / "test.ioc.cmd").read_text()
    actual_boot = out_file.read_text()

    example_db = (samples / "boot_scripts" / "test.ioc.make_db.sh").read_text()
    actual_db = out_db.read_text()

    assert example_boot == actual_boot
    assert example_db == actual_db


def test_example_sr_rf_08(tmp_path: Path, samples: Path, ibek_defs: Path):
    """
    build IOC sr-rf-ioc-08 from yaml and verify the result. This IOC tests:

    - all the yaml files in ibek-defs are schema compliant
    - the Utils class counter function (for Vectors and Carriers)
    - the once field (for Hy8401 comments)
    """

    clear_entity_model_ids()
    UTILS.__reset__()

    tmp_path = Path("/tmp/ibek_test2")
    tmp_path.mkdir(exist_ok=True)

    entity_file = samples / "example-srrfioc08" / "SR-RF-IOC-08.ibek.ioc.yaml"
    definition_files = list(ibek_defs.glob("_global/*.support.yaml"))
    definition_files.append(ibek_defs / "ipac" / "ipac.ibek.support.yaml")
    definition_files.append(ibek_defs / "Hy8401ip" / "Hy8401ip.ibek.support.yaml")
    out_file = tmp_path / "new_dir" / "st.cmd"
    out_db = tmp_path / "new_dir" / "make_db.sh"

    params = [
        "build-startup",
        entity_file,
        "--out",
        out_file,
        "--db-out",
        out_db,
    ]
    params += definition_files

    run_cli(*params)

    example_boot = (samples / "example-srrfioc08" / "st.cmd").read_text()
    actual_boot = out_file.read_text()

    example_db = (samples / "example-srrfioc08" / "make_db.sh").read_text()
    actual_db = out_db.read_text()

    assert example_boot == actual_boot
    assert example_db == actual_db


def test_values_ioc(tmp_path: Path, samples: Path, ibek_defs: Path):
    """
    build values ioc from yaml and verify the result

    This IOC verifies that repeated reference to a 'values' field
    with counter gets the same value every time.

    TODO: IMPORTANT: this test currently proves that the values are NOT the same
    TODO: make sure samples/values_test/st.cmd is updated when this is fixed.
    """

    clear_entity_model_ids()
    UTILS.__reset__()

    tmp_path = Path("/tmp/ibek_test2")
    tmp_path.mkdir(exist_ok=True)
    test_path = samples / "values_test"

    entity_file = test_path / "values.ibek.ioc.yaml"
    definition_files = [
        ibek_defs / "_global" / "epics.ibek.support.yaml",
        ibek_defs / "ipac" / "ipac.ibek.support.yaml",
    ]
    out_file = tmp_path / "new_dir" / "st.cmd"
    out_db = tmp_path / "new_dir" / "make_db.sh"

    params = [
        "build-startup",
        entity_file,
        "--out",
        out_file,
        "--db-out",
        out_db,
    ]
    params += definition_files

    run_cli(*params)

    example_boot = (test_path / "st.cmd").read_text()
    actual_boot = out_file.read_text()
    assert example_boot == actual_boot
