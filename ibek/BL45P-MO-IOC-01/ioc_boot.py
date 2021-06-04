from pathlib import Path
from typing import List

from jinja2 import Template
from ruamel.yaml import YAML

from ibek.pmac import EntityInstance, PmacIOC

yaml = YAML()


def render_script_elements(ioc_instance) -> str:
    scripts = ""
    for instance in ioc_instance.instances:
        for script in instance.create_scripts():
            scripts += (Template(script).render(instance.__dict__)) + "\n"
    return scripts


def create_database_elements(ioc_instance) -> str:
    databases = ""
    for instance in ioc_instance.instances:
        for database in instance.create_database():
            databases += Template(database).render(instance.__dict__) + "\n"
    return databases


def create_boot_script(ioc_instance_yaml_path):
    with open(ioc_instance_yaml_path, "r") as f:
        ioc_instance = PmacIOC.deserialize(yaml.load(f))

    with open(Path(__file__).parent / "startup_script.txt", "r") as f:
        template = Template(f.read())

    template = template.render(
        script_elements=render_script_elements(ioc_instance),
        database_elements=create_database_elements(ioc_instance),
    )
    return template


def main(
    ioc_instance_yaml_path: str = (Path(__file__).parent / "bl45p-mo-ioc-02.pmac.yaml"),
):

    boot_script = create_boot_script(ioc_instance_yaml_path)
    print(boot_script)


if __name__ == "__main__":
    main()
