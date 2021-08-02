from dataclasses import dataclass, field
from typing import Any, Mapping

from ruamel.yaml import YAML

from ibek.support import Support


@dataclass
class yaml_to_dataclass:
    yaml_file: str
    namespace: Mapping[str, Any] = field(default_factory=dict)

    def _get_support_instance(self) -> Support:
        """Deserializes a yaml file into an instance of the Support class"""
        yaml = YAML()
        with open(self.yaml_file, "r") as f:
            return Support.deserialize(yaml.load(f))

    def get_module_dataclass(self) -> type:
        """Creates a dataclass as described in self.yaml_file"""
        support = self._get_support_instance()
        module_dataclass = support.get_module()
        self.namespace = support.namespace
        return module_dataclass
