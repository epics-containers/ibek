from jinja2 import Template

from ibek.pmac import DatabaseEntry, EntityInstance, Geobrick, PmacAsynIPPort


def test_create_database():
    """ creates a simple instance of a database and checks that a startup
    script entry of the correct form is returned """
    ei = EntityInstance(name="Test Entity", script=["my name is: {{ name }}"])
    db = [
        DatabaseEntry(
            file="database_entry_one.template", define_args="name = {{ name }}"
        )
    ]
    assert (
        Template(ei.create_database(db)[0]).render(ei.__dict__)
        == 'dbLoadRecords("database_entry_one.template", "name = Test Entity")'
    )


def test_pmac_asyn_ipport_script():
    pmac_asyn_ipport_instance = PmacAsynIPPort(
        name="my_pmac_instance", IP="111.111.111.111"
    )
    script_templates = pmac_asyn_ipport_instance.create_scripts()
    assert (
        Template(script_templates[0]).render(pmac_asyn_ipport_instance.__dict__)
        == "pmacAsynIPConfigure(my_pmac_instance, 111.111.111.111:1025)"
    )


def test_geobrick_script():
    pmac_geobrick_instance = Geobrick(
        name="test_geobrick",
        PORT="my_asyn_port",
        P="geobrick_one",
        idlePoll=200,
        movingPoll=800,
    )

    print(pmac_geobrick_instance.create_scripts())


def test_geobrick_database():
    pmac_geobrick_instance = Geobrick(
        name="test_geobrick",
        PORT="my_asyn_port",
        P="geobrick_one",
        idlePoll=200,
        movingPoll=800,
    )
    db_script_entries = (
        pmac_geobrick_instance.create_database()
    )  # returns a list of jinja templates
    assert (
        Template(db_script_entries[0]).render(pmac_geobrick_instance.__dict__)
        == 'dbLoadRecords("pmacController.template", "PORT=my_asyn_port, P=geobrick_one, TIMEOUT=200, FEEDRATE=150, CSG0=, CSG1=, CSG2=, CSG3=, CSG4=, CSG5=, CSG6=, CSG7=, ")'
    )
    assert (
        Template(db_script_entries[1]).render(pmac_geobrick_instance.__dict__)
        == 'dbLoadRecords("pmacStatus.template", "PORT=my_asyn_port, P=geobrick_one, Description=, ControlIP=, ControlPort=, ControlMode=")'
    )
