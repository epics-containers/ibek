"""
Tests for the rendering of scripts and database entries from generated
Entity classes
"""
from pathlib import Path
from unittest.mock import Mock

from ruamel.yaml import YAML

from ibek.render import render_database, render_script
from ibek.support import Support
from tests.samples.classes.pmac_support import SUPPORT


def test_deserialize_support(samples: Path) -> None:
    yaml_dict = YAML().load(samples / "yaml" / "pmac.ibek.yaml")
    actual = Support.deserialize(yaml_dict)
    assert actual == SUPPORT


def test_pmac_asyn_ip_port_script(pmac_classes):
    generated_class = pmac_classes.PmacAsynIPPort
    pmac_asyn_ip = generated_class(name="my_pmac_instance", IP="111.111.111.111")

    script_txt = render_script(pmac_asyn_ip)
    assert script_txt == "pmacAsynIPConfigure(my_pmac_instance, 111.111.111.111:1025)"


def test_geobrick_script(pmac_classes):
    generated_class = pmac_classes.Geobrick
    ip_port = Mock()
    ip_port.name = "my_asyn_port"
    pmac_geobrick_instance = generated_class(
        name="test_geobrick",
        PORT=ip_port,
        P="geobrick_one",
        numAxes=8,
        idlePoll=200,
        movingPoll=800,
    )

    script_txt = render_script(pmac_geobrick_instance)

    assert (
        script_txt
        == "pmacCreateController(test_geobrick, my_asyn_port, 0, 8, 800, 200)\n"
        "pmacCreateAxes(test_geobrick, 8)"
    )


def test_geobrick_database(pmac_classes):
    generated_class = pmac_classes.Geobrick
    pmac_geobrick_instance = generated_class(
        name="test_geobrick",
        PORT="my_asyn_port",
        P="geobrick_one",
        numAxes=8,
        idlePoll=200,
        movingPoll=800,
    )

    db_txt = render_database(pmac_geobrick_instance)

    assert (
        db_txt == 'dbLoadRecords("pmacController.template", "PMAC=geobrick_one")\n'
        'dbLoadRecords("pmacStatus.template", "PMAC=geobrick_one")'
    )
