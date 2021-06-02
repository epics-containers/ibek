from pathlib import Path
from typing import List

from jinja2 import Template
from ruamel.yaml import YAML

from ibek.pmac import EntityInstance, PmacIOC

yaml = YAML()


def open_ioc_yaml() -> PmacIOC:
    with open((Path(__file__).parent).parent / "bl45p-mo-ioc-02.pmac.yaml", "r") as f:
        ioc_yaml = yaml.load(f)
        ioc_yaml = PmacIOC.deserialize(ioc_yaml)
        return ioc_yaml


def evaluate_scripts(instance: EntityInstance) -> List[str]:
    return_list = []
    for script in instance.script:
        return_list += Template(script).render(instance.__dict__) + "\n"
    return return_list


def evaluate_db(instance: EntityInstance) -> List[str]:
    return_list = []
    print("printing instance:" + str(instance) + "\n")
    for database in instance.databases:

        filepath = database.file
        define_args = (Template(database.define_args)).render(instance.__dict__)
        return_list += f'dbLoadRecords("{filepath}", "{define_args}")\n'

    return return_list


def generate_boot_script() -> str:
    """ Function which returns a string representing the boot script. 
    Substitutes instance specific elements into a jinja template. """

    # Open jinja template for script
    with open((Path(__file__).parent / "startup_script.txt"), "r") as f:
        boot_template = Template(f.read())

    boot_script_instance_elements = ""
    boot_db_instance_elements = ""
    my_ioc = open_ioc_yaml()

    # Add script components to the startup script
    for instance in my_ioc.instances:
        for script in evaluate_scripts(instance):
            boot_script_instance_elements += script
    # add dbloadrecords
    for instance in my_ioc.instances:

        for db_record in evaluate_db(instance):
            boot_db_instance_elements += db_record

    return boot_template.render(
        script_elements=boot_script_instance_elements,
        database_elements=boot_db_instance_elements,
    )

    # look in bulder.py for pmac project


if __name__ == "__main__":
    print(generate_boot_script())
    with open("ioc.boot", "w") as f:
        f.write(generate_boot_script())
