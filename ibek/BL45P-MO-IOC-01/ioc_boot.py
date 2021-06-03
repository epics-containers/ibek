from pathlib import Path
from typing import List

from jinja2 import Template
from ruamel.yaml import YAML

from ibek.pmac import EntityInstance, PmacIOC

yaml = YAML()


def get_script_templates(entity: EntityInstance) -> List:
    pass


def get_database_templates(entity: EntityInstance) -> List:
    pass


def template_substitution(templates: List[str], entity: EntityInstance) -> List:
    pass


def format_script():
    pass


def main(
    ioc_instance_yaml_path: str = (Path(__file__).parent / "bl45p-mo-ioc-02.pmac.yaml"),
):
    print("Deserialize instance.ioc_class.yaml")
    with open(ioc_instance_yaml_path, "r") as f:
        ioc_instance = PmacIOC.deserialize(yaml.load(f))
        print(ioc_instance)


if __name__ == "__main__":
    main()
