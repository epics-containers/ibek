"""
Tests for the rendering of scripts and database entries from generated
Entity classes
"""
from typing import Literal

from ibek.ioc import clear_entity_model_ids, make_ioc_model
from ibek.render import Render


def find_entity_class(entity_classes, entity_type):
    # TODO is this the easiest way to find the entity class?
    for entity_class in entity_classes:
        literal = Literal[entity_type]  # type: ignore
        if entity_class.model_fields["type"].annotation == literal:
            return entity_class
    else:
        raise ValueError(f"{entity_type} not found in entity_classes")


def test_pmac_asyn_ip_port_script(pmac_classes):
    generated_class = find_entity_class(pmac_classes, "pmac.PmacAsynIPPort")

    pmac_asyn_ip = generated_class(name="my_pmac_instance", IP="111.111.111.111")

    render = Render()
    script_txt = render.render_script(
        pmac_asyn_ip, pmac_asyn_ip.__definition__.pre_init
    )
    assert script_txt == (
        "\n# pmacAsynIPConfigure AsynPortName IPAddress\n"
        "pmacAsynIPConfigure my_pmac_instance 111.111.111.111:1025\n"
    )


def test_geobrick_script(pmac_classes):
    pmac_class = find_entity_class(pmac_classes, "pmac.Geobrick")
    ip_port_class = find_entity_class(pmac_classes, "pmac.PmacAsynIPPort")

    ip_port_class(name="my_asyn_port", IP="1.1")
    pmac_geobrick_instance = pmac_class(
        name="test_geobrick",
        PORT="my_asyn_port",
        P="geobrick_one",
        numAxes=8,
        idlePoll=200,
        movingPoll=800,
    )

    render = Render()
    script_txt = render.render_script(
        pmac_geobrick_instance, pmac_geobrick_instance.__definition__.pre_init
    )

    assert (
        script_txt
        == "\n# pmacCreateController AsynPortName PmacAsynPort Address NumAxes "
        "MovingPollPeriod IdlePollPeriod\n"
        "pmacCreateController test_geobrick my_asyn_port 0 8 800 200\n"
        "pmacCreateAxes test_geobrick 8\n"
    )


def test_geobrick_database(pmac_classes):
    generated_class = find_entity_class(pmac_classes, "pmac.Geobrick")
    ip_port_class = find_entity_class(pmac_classes, "pmac.PmacAsynIPPort")

    ip_port_class(name="my_asyn_port", IP="1.1")
    pmac_geobrick_instance = generated_class(
        name="test_geobrick",
        PORT="my_asyn_port",
        P="geobrick_one",
        numAxes=8,
        idlePoll=200,
        movingPoll=800,
    )

    render = Render()
    db_txt = render.render_database(pmac_geobrick_instance)

    assert (
        db_txt == 'msi -I${EPICS_DB_INCLUDE_PATH} -M"NAXES=8, PORT=test_geobrick, '
        "P=geobrick_one, idlePoll=200, movingPoll=800, TIMEOUT=4, CSG0=, CSG1=, "
        'CSG2=, CSG3=, CSG4=" "pmacController.template"\n'
        'msi -I${EPICS_DB_INCLUDE_PATH} -M"PORT=test_geobrick, '
        'P=geobrick_one" "pmacStatus.template"\n'
    )


def test_epics_environment_variables(epics_classes):
    # Using a specific variable entity
    generated_class = find_entity_class(epics_classes, "epics.EpicsCaMaxArrayBytes")

    max_array_bytes_instance = generated_class(max_bytes=10000000)

    render = Render()
    env_text = render.render_environment_variables(max_array_bytes_instance)

    assert env_text == "epicsEnvSet EPICS_CA_MAX_ARRAY_BYTES 10000000\n"

    # Using the generic entity
    env_name = "EPICS_CA_SERVER_PORT"
    env_value = "6000"
    generated_class = find_entity_class(epics_classes, "epics.EpicsEnvSet")

    epics_env_set_instance = generated_class(name=env_name, value=env_value)

    env_text = render.render_environment_variables(epics_env_set_instance)

    assert env_text == f"epicsEnvSet {env_name} {env_value}\n"


def test_entity_disabled_does_not_render_elements(pmac_classes, epics_classes):
    # There are four elements to check: script, database, environment variables
    # and post-iocInit

    clear_entity_model_ids()

    # Entity which has a script and database
    pmac_geobrick_class = find_entity_class(pmac_classes, "pmac.Geobrick")
    # Entity which has env_vars
    ca_max_array_bytes_class = find_entity_class(
        epics_classes, "epics.EpicsCaMaxArrayBytes"
    )
    # Entity which has post_ioc_init
    dbpf_class = find_entity_class(epics_classes, "epics.Dbpf")
    # We require pmac asyn IP port instances for the Geobrick class
    pmac_asyn_ip_class = find_entity_class(pmac_classes, "pmac.PmacAsynIPPort")

    # Make an IOC model with our entity classes
    Ioc = make_ioc_model(
        [pmac_geobrick_class, ca_max_array_bytes_class, dbpf_class, pmac_asyn_ip_class]
    )

    # build a list of dictionaries to instantiate an IOC
    instance_list = []

    instance_list.append(
        dict(type="pmac.PmacAsynIPPort", name="geobrick_one_port", IP="172.23.100.101")
    )
    instance_list.append(
        dict(type="pmac.PmacAsynIPPort", name="geobrick_two_port", IP="172.23.100.101")
    )

    # Create two instances of the Geobrick entity, one disabled
    instance_list.append(
        dict(
            type="pmac.Geobrick",
            name="geobrick_enabled",
            PORT="geobrick_one_port",
            P="geobrick_one",
            numAxes=8,
            idlePoll=200,
            movingPoll=800,
        )
    )
    instance_list.append(
        dict(
            type="pmac.Geobrick",
            name="geobrick_disabled",
            PORT="geobrick_two_port",
            P="geobrick_two",
            numAxes=8,
            idlePoll=200,
            movingPoll=800,
            entity_enabled=False,
        )
    )

    # Create two instances of the CA max array bytes entity, one disabled
    instance_list.append(dict(type="epics.EpicsCaMaxArrayBytes"))
    instance_list.append(dict(type="epics.EpicsCaMaxArrayBytes", entity_enabled=False))

    # Create two instances of the dpbf class
    instance_list.append(dict(type="epics.Dbpf", pv="TEST:PV:1", value="pv_value_1"))
    instance_list.append(
        dict(
            type="epics.Dbpf", pv="TEST:PV:2", value="pv_value_2", entity_enabled=False
        )
    )

    # Make an IOC with our instances
    ioc = Ioc(
        ioc_name="TEST-IOC-01",
        description="Test IOC",
        entities=instance_list,
        generic_ioc_image="test_ioc_image",
    )

    # Render script and check output
    # ControlerPort, LowLevelDriverPort, Address, Axes, MovingPoll, IdlePoll
    expected_script = (
        "\n# pmacAsynIPConfigure AsynPortName IPAddress\n"
        "pmacAsynIPConfigure geobrick_one_port 172.23.100.101:1025\n"
        "pmacAsynIPConfigure geobrick_two_port 172.23.100.101:1025\n"
        "\n# pmacCreateController AsynPortName PmacAsynPort Address NumAxes "
        "MovingPollPeriod IdlePollPeriod\n"
        "pmacCreateController geobrick_enabled geobrick_one_port 0 8 800 200\n"
        "pmacCreateAxes geobrick_enabled 8\n"
    )
    render = Render()
    script = render.render_pre_ioc_init_elements(ioc)
    assert script == expected_script

    # Render database
    expected_database = (
        'msi -I${EPICS_DB_INCLUDE_PATH} -M"NAXES=8, PORT=geobrick_enabled, '
        "P=geobrick_one, idlePoll=200, movingPoll=800, TIMEOUT=4, CSG0=, CSG1=, "
        'CSG2=, CSG3=, CSG4=" "pmacController.template"\n'
        'msi -I${EPICS_DB_INCLUDE_PATH} -M"PORT=geobrick_enabled, P=geobrick_one" '
        '"pmacStatus.template"\n'
    )
    database = render.render_database_elements(ioc)
    assert database == expected_database

    # Render environment variables
    expected_env_vars = "epicsEnvSet EPICS_CA_MAX_ARRAY_BYTES 6000000\n"
    env_vars = render.render_environment_variable_elements(ioc)
    assert env_vars == expected_env_vars

    # Render post_ioc_init
    expected_post_ioc_init = "\n# dbpf pv value\ndbpf TEST:PV:1 pv_value_1\n"
    post_ioc_init = render.render_post_ioc_init_elements(ioc)
    assert post_ioc_init == expected_post_ioc_init
