"""
functions for making Entity models
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Union

from pydantic import Field
from ruamel.yaml.main import YAML

from ibek.parameters import EnumParam
from ibek.utils import UTILS

from .entity_model import EntityModel
from .ioc import IOC


class IocFactory:
    """
    A Class for creating Generic IOC classes and instances
    """

    def deserialize_ioc(
        self, ioc_instance_yaml: Path, entity_models: list[EntityModel]
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
        name = UTILS.render({}, ioc_instance_dict["ioc_name"], "str")
        UTILS.set_ioc_name(name)
        ioc_instance_dict["ioc_name"] = name

        # Create an IOC instance from the instance dict and the model
        ioc_instance = ioc_model(**ioc_instance_dict)
        self.fixup_enums(ioc_instance)

        return ioc_instance

    def fixup_enums(self, ioc_instance: IOC):
        """
        Fixup the enums in the IOC instance, so that they are the value of
        their original Enum, rather than the key.

        *.ibek.support.yaml files may specify Enum parameters like this:
        ```
            stop:
              type: enum
              description: |-
              Stop Bits
              values:
                one: 1
                two: 2
              default: "1"
        ```
        This means that ioc.yaml would specify stop bits using the strings
        "one" and "two", but when the startup script or DB renders the value
        it will use the Enum value, which is 1 and 2 respectively.

        To do this requires the use of "use_enum_values=True" in the Pydantic
        model config so that only a string need be specified instead of a
        serialized Enum.

        To make this work we swap the value and key in all enums before creating
        the model (see enum_swapped in EntityFactory._make_entity_type). Pydantic
        will then serialize/deserialize using the value of the swapped Enum
        i.e. "one" or "two".

        After deserializing the IOC instance this function swaps back to the
        original value so that it will be used in rendering of parameters. Enums
        can also be specified with no value, in which case the key is used
        in ioc.yaml and in rendering.
        """
        for entity in ioc_instance.entities:
            for field_name, field_value in entity.model_dump().items():
                # RepeatEntities are dumb dictionaries with no _model, skip them
                if hasattr(entity, "_model"):
                    # check to see if field is an Enum value in the EntityModel
                    parameter = entity._model.parameters.get(field_name)
                    if isinstance(parameter, EnumParam):
                        # if so, set the value to the Enum value, instead of its key
                        enum_value = parameter.values.get(field_value)
                        if enum_value is not None:
                            setattr(entity, field_name, enum_value)

    def make_ioc_model(self, entity_models: list[EntityModel]) -> type[IOC]:
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
