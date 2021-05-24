from pathlib import Path

from jinja2 import Template
from ruamel.yaml import YAML

from ibek.pmac import PmacIOC

yaml = YAML()


def open_ioc_yaml() -> PmacIOC:
    with open((Path(__file__).parent).parent / "bl45p-mo-ioc-02.pmac.yaml", "r") as f:
        ioc_yaml = yaml.load(f)
        ioc_yaml = PmacIOC.deserialize(ioc_yaml)
        return ioc_yaml


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


def generate_boot_script() -> str:
    """ Function which returns a string representing the boot script. 
    Adds boilerplate to the start and end of the script and adds """
    boot_script = boot_initial_boilerplate
    my_ioc = open_ioc_yaml()
    instances = my_ioc.instances
    for instance in instances:
        script = Template(instance.script)
        script = script.render(instance.__dict__)
        boot_script += str(script) + "\n"
    boot_script += boot_final_boilerplate
    return boot_script


if __name__ == "__main__":
    print(generate_boot_script())
