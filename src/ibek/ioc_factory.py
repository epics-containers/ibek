"""
functions for making Entity models
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, List, Sequence, Type, Union

from pydantic import Field
from ruamel.yaml.main import YAML

from ibek.utils import UTILS

from .ioc import IOC, Entity


class IocFactory:
    """
    A Class for creating Generic IOC classes and instances
    """

    def deserialize_ioc(
        self, ioc_instance_yaml: Path, entity_models: List[Type[Entity]]
    ) -> IOC:
        """
        Takes an ioc instance entities file, list of generic ioc yaml files.

        Returns a model of the resulting ioc instance
        """

        # Create a Class representing this Generic IOC
        ioc_model = self.make_ioc_model(entity_models)

        # extract the ioc instance yaml into a dict
        ioc_instance_dict = YAML(typ="safe").load(ioc_instance_yaml)

        if ioc_instance_dict is None or "ioc_name" not in ioc_instance_dict:
            raise RuntimeError(
                f"Failed to load a valid ioc config from {ioc_instance_yaml}"
            )

        # extract the ioc name into UTILS for use in jinja renders
        name = UTILS.render({}, ioc_instance_dict["ioc_name"])
        UTILS.set_ioc_name(name)
        ioc_instance_dict["ioc_name"] = name

        # Create an IOC instance from the instance dict and the model
        ioc_instance = ioc_model(**ioc_instance_dict)

        return ioc_instance

    def make_ioc_model(self, entity_models: List[Type[Entity]]) -> Type[IOC]:
        """
        Create an IOC derived model, by setting its entities attribute to
        be of type 'list of Entity derived classes'.

        Also instantiate any SubEntities at this time
        """

        entity_union = Union[tuple(entity_models)]  # type: ignore
        discriminated = Annotated[entity_union, Field(discriminator="type")]  # type: ignore

        class NewIOC(IOC):
            entities: Sequence[discriminated] = Field(  # type: ignore
                description="List of entities this IOC instantiates"
            )

        return NewIOC
