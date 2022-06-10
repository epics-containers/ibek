"""
Tests for the rendering of scripts and database entries from generated
Entity classes
"""
from unittest.mock import Mock

from ibek.ioc import IOC
from ibek.render import (
    render_database,
    render_database_elements,
    render_environment_variable_elements,
    render_environment_variables,
    render_post_ioc_init_elements,
    render_script,
    render_script_elements,
)


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
        db_txt == 'msi -I${EPICS_DB_INCLUDE_PATH} -M"PMAC=geobrick_one"'
        ' "pmacController.template"\n'
        'msi -I${EPICS_DB_INCLUDE_PATH} -M"PMAC=geobrick_one"'
        ' "pmacStatus.template"'
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


def test_entity_disabled_does_not_render_elements(pmac_classes, epics_classes):
    # There are four elements to check: script, database, environment variables
    # and post-iocInit

    # Entity which has a script and database
    pmac_geobrick_class = pmac_classes.Geobrick
    # Entity which has env_vars
    ca_max_array_bytes_class = epics_classes.EPICS_CA_MAX_ARRAY_BYTES
    # Entity which has post_ioc_init
    dbpf_class = epics_classes.dbpf

    # We require pmac asyn IP port instances for the Geobrick class
    pmac_asyn_ip_class = pmac_classes.PmacAsynIPPort
    brick_one_asyn_ip_port = pmac_asyn_ip_class(
        name="geobrick_one_port", IP="172.23.100.101"
    )
    brick_two_asyn_ip_port = pmac_asyn_ip_class(
        name="geobrick_two_port", IP="172.23.100.101"
    )

    # Store created instances in a list
    instance_list = []

    # Create two instances of the Geobrick entity, one disabled
    instance_list.append(
        pmac_geobrick_class(
            name="geobrick_enabled",
            PORT=brick_one_asyn_ip_port,
            P="geobrick_one",
            numAxes=8,
            idlePoll=200,
            movingPoll=800,
        )
    )
    instance_list.append(
        pmac_geobrick_class(
            name="geobrick_disabled",
            PORT=brick_two_asyn_ip_port,
            P="geobrick_two",
            numAxes=8,
            idlePoll=200,
            movingPoll=800,
            entity_enabled=False,
        )
    )

    # Create two instances of the CA max array bytes entity, one disabled
    instance_list.append(ca_max_array_bytes_class())
    instance_list.append(ca_max_array_bytes_class(entity_enabled=False))

    # Create two instances of the dpbf class
    instance_list.append(dbpf_class(pv="TEST:PV:1", value="pv_value_1"))
    instance_list.append(
        dbpf_class(pv="TEST:PV:2", value="pv_value_2", entity_enabled=False)
    )

    # Make an IOC with our instances
    ioc = IOC(
        "TEST-IOC-01",
        "Test IOC",
        instance_list,
        "test_ioc_image",
    )

    # Render script and check output
    expected_script = (
        "pmacCreateController(geobrick_enabled, geobrick_one_port, 0, 8, 800, 200)\n"
        "pmacCreateAxes(geobrick_enabled, 8)\n"
    )
    script = render_script_elements(ioc)
    assert script == expected_script

    # Render database
    expected_database = (
        'msi -I${EPICS_DB_INCLUDE_PATH} -M"PMAC=geobrick_one"'
        ' "pmacController.template"\n'
        'msi -I${EPICS_DB_INCLUDE_PATH} -M"PMAC=geobrick_one" "pmacStatus.template"\n'
    )
    database = render_database_elements(ioc)
    assert database == expected_database

    # Render environment variables
    expected_env_vars = "epicsEnvSet \"EPICS_CA_MAX_ARRAY_BYTES\", '6000000'\n"
    env_vars = render_environment_variable_elements(ioc)
    assert env_vars == expected_env_vars

    # Render post_ioc_init
    expected_post_ioc_init = 'dbpf "TEST:PV:1", "pv_value_1"\n'
    post_ioc_init = render_post_ioc_init_elements(ioc)
    assert post_ioc_init == expected_post_ioc_init
