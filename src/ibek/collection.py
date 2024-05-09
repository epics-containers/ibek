"""
The Support Class represents a deserialized <MODULE_NAME>.ibek.support.yaml file.
"""

from __future__ import annotations

from typing import Sequence, Union

from pydantic import Field

from .args import Arg, Value
from .ioc import Entity


class CollectionDefinition:
    name: str = Field(
        description="Publish Definition as type <module>.<name> for IOC instances"
    )
    description: str = Field(
        description="A description of the Support module defined here"
    )
    # declare Arg as Union of its subclasses for Pydantic to be able to deserialize
    args: Sequence[Union[tuple(Arg.__subclasses__())]] = Field(  # type: ignore
        description="The arguments IOC instance should supply", default=()
    )
    values: Sequence[Value] = Field(
        description="Calculated values to use as additional arguments", default=()
    )

    entities: Sequence[Entity] = Field(
        description="The entities that this collection is to instantiate", default=()
    )
