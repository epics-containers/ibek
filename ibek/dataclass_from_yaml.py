from dataclasses import dataclass

from ruamel.yaml import YAML

from ibek.support import Support


@dataclass
class yaml_to_dataclass:
    yaml_file: str

    def _get_support_instance(self) -> Support:
        """ Deserializes a yaml file into an instance of the Support class """
        yaml = YAML()
        with open(self.yaml_file, "r") as f:
            return Support.deserialize(yaml.load(f))

    def get_module_dataclass(self) -> type:
        """ Creates a dataclass as described in self.yaml_file """
        # support_instance = self._get_support_instance()
        # module_dataclass = support_instance.get_module()
        return self._get_support_instance().get_module()
