from pathlib import Path
from typing import Sequence

from jinja2 import Template
from ruamel.yaml import YAML

from ibek.pmac import EntityInstance, PmacIOC

yaml = YAML()


def open_ioc_yaml() -> PmacIOC:
    with open((Path(__file__).parent).parent / "bl45p-mo-ioc-02.pmac.yaml", "r") as f:
        ioc_yaml = yaml.load(f)
        ioc_yaml = PmacIOC.deserialize(ioc_yaml)
        return ioc_yaml


# migrate over to jinja template object
boot_initial_boilerplate = """
cd "$(TOP)"
epicsEnvSet "EPICS_CA_MAX_ARRAY_BYTES", '6000000'
epicsEnvSet "EPICS_TS_MIN_WEST", '0'
cd "$(TOP)"
dbLoadDatabase "dbd/ioc.dbd"
ioc_registerRecordDeviceDriver(pdbbase)
"""

boot_final_boilerplate = """
cd "$(TOP)"
iocInit
 """


def evaluate_scripts(instance: EntityInstance) -> Sequence[str]:
    return_list = []
    for script in instance.script:
        script = Template(script)
        script = script.render(instance.__dict__)
        return_list += script + "\n"
    return return_list


def evaluate_db(instance: EntityInstance) -> Sequence[str]:
    return_list = []
    """
    Evaluate the db portion of this EntityInstance
    """
    return return_list


def generate_boot_script() -> str:
    """ Function which returns a string representing the boot script. 
    Adds boilerplate to the start and end of the script and adds """

    # Open jinja template for script
    with open((Path(__file__).parent / "startup_script.txt"), "r") as f:
        boot_template = Template(f.read())

    boot_script_instance_elements = ""
    my_ioc = open_ioc_yaml()

    # Add script components to the startup script
    for instance in my_ioc.instances:
        for script in evaluate_scripts(instance):
            boot_script_instance_elements += script
    # add dbloadrecords
    for instance in my_ioc.instances:
        for db_record in evaluate_db(instance):
            boot_script_instance_elements += db_record

    return boot_template.render(script_elements=boot_script_instance_elements)

    # look in bulder.py for pmac project


if __name__ == "__main__":
    print(generate_boot_script())
