from pathlib import Path

from ibek.dataclass_from_yaml import yaml_to_dataclass
from ibek.render import create_database, make_script

sample_yaml = Path(__file__).parent / "samples" / "yaml"


def generate_pmac_classes():
    # create a support object from YAML
    support = yaml_to_dataclass(str(sample_yaml / "pmac.ibek.yaml"))

    # populate its dataclass namespace
    support.get_module_dataclass()

    # return the namespace so that callers have access to all of the
    # generated dataclasses
    return support.namespace


def test_pmac_asyn_ip_port_script():
    namespace = generate_pmac_classes()

    generated_class = namespace["pmac.PmacAsynIPPort"]
    pmac_asyn_ip = generated_class(
        generated_class, name="my_pmac_instance", IP="111.111.111.111"
    )

    script_txt = make_script(pmac_asyn_ip)
    assert script_txt == "pmacAsynIPConfigure(my_pmac_instance, 111.111.111.111:1025)"


def test_geobrick_script():
    namespace = generate_pmac_classes()

    generated_class = namespace["pmac.Geobrick"]
    pmac_geobrick_instance = generated_class(
        generated_class,
        name="test_geobrick",
        port="my_asyn_port",
        P="geobrick_one",
        idlePoll=200,
        movingPoll=800,
    )

    script_txt = make_script(pmac_geobrick_instance)

    assert script_txt == (
        "pmacCreateController(test_geobrick, my_asyn_port, 0, 8, 800, 200)\n"
        "pmacCreateAxes(test_geobrick, 8)"
    )


def test_geobrick_database():
    namespace = generate_pmac_classes()

    generated_class = namespace["pmac.Geobrick"]
    pmac_geobrick_instance = generated_class(
        generated_class,
        name="test_geobrick",
        port="my_asyn_port",
        P="geobrick_one",
        idlePoll=200,
        movingPoll=800,
    )

    db_txt = create_database(pmac_geobrick_instance)

    assert db_txt == (
        'dbLoadRecords("pmacController.template", "PMAC=geobrick_one")\n'
        'dbLoadRecords("pmacStatus.template", "PMAC=geobrick_one")'
    )
