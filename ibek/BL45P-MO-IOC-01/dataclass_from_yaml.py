from dataclasses import dataclass

from apischema.json_schema import deserialization_schema
from ruamel.yaml import YAML

from ibek.support import Support


@dataclass
class yaml_to_dataclass:
    yaml_file: str

    def _get_support_instance(self) -> Support:
        yaml = YAML()
        with open(self.yaml_file, "r") as f:
            return Support.deserialize(yaml.load(f))

    def get_module_dataclass(self):
        support_instance = self._get_support_instance()
        module_dataclass = support_instance.get_module()
        return module_dataclass


test = yaml_to_dataclass(
    "/Users/richardparke/Documents/K8-IOCs/ibek/tests/pmac.ibek.yaml"
)

print(deserialization_schema(test.get_module_dataclass()))

