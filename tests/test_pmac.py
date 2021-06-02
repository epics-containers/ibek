import json

import apischema
from apischema.json_schema import deserialization_schema

from ibek.pmac import DatabaseEntry, EntityInstance, Geobrick, PmacAsynIPPort, PmacIOC


def test_create_database():
    """ creates a simple instance of a database and checks that a startup script entry of the 
    correct form is returned """
    ei = EntityInstance(name="Test Entity", script=["my name is: {{ name }}"])
    db = (
        DatabaseEntry(
            file='"database_entry_one.template"', define_args='"name = {{ name }}"'
        ),
    )
    assert (
        ei.create_database(db)[0].render(ei.__dict__)
        == 'dbLoadRecords("database_entry_one.template", "name = Test Entity")'
    )


def test_pmac_asyn_ipport_script():
    pmac_asyn_ipport_instance = PmacAsynIPPort(
        name="my_pmac_instance", IP="111.111.111.111"
    )
    assert pmac_asyn_ipport_instance.create_scripts() == [
        "pmacAsynIPConfigure(my_pmac_instance, 111.111.111.111:1025)"
    ]


def test_geobrick_script():
    pmac_geobrick_instance = Geobrick(
        name="test_geobrick",
        port="my_asyn_port",
        P="geobrick_one",
        idlePoll=200,
        movingPoll=800,
    )

    print(pmac_geobrick_instance.create_scripts())


def test_geobrick_database():
    pmac_geobrick_instance = Geobrick(
        name="test_geobrick",
        port="my_asyn_port",
        P="geobrick_one",
        idlePoll=200,
        movingPoll=800,
    )
    db_script_entries = pmac_geobrick_instance.create_database()
    assert (
        db_script_entries[0].render(pmac_geobrick_instance.__dict__)
        == 'dbLoadRecords("pmacController.template", "PORT=my_asyn_port, P=geobrick_one, TIMEOUT=200, FEEDRATE=150, CSG0=, CSG1=, CSG2=, CSG3=, CSG4=, CSG5=, CSG6=, CSG7=, ")'
    )
    assert (
        db_script_entries[1].render(pmac_geobrick_instance.__dict__)
        == "dbLoadRecords(pmacStatus.template, PORT = my_asyn_port, P = geobrick_one)"
    )

