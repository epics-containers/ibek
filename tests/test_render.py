"""
Tests for the rendering of scripts and database entries from generated
Entity classes
"""
from unittest.mock import Mock

from ibek.render import render_database, render_environment_variables, render_script


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


def test_epics_environment_variables(epics_classes):
    # Using a specific variable entity
    generated_class = epics_classes.EPICS_CA_MAX_ARRAY_BYTES
    max_array_bytes_instance = generated_class(max_bytes=10000000)

    env_text = render_environment_variables(max_array_bytes_instance)

    assert env_text == "epicsEnvSet \"EPICS_CA_MAX_ARRAY_BYTES\", '10000000'"

    # Using the generic entity
    env_name = "EPICS_CA_SERVER_PORT"
    env_value = 6000
    generated_class = epics_classes.epicsEnvSet
    epics_env_set_instance = generated_class(name=env_name, value=env_value)

    env_text = render_environment_variables(epics_env_set_instance)

    assert env_text == f"epicsEnvSet \"{env_name}\", '{env_value}'"
