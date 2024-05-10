"""
Define a collection of entities with arguments for instantiating them
"""

from __future__ import annotations

from typing import Sequence, Union

from pydantic import BaseModel, Field

from .args import Arg, Value
from .sub_entity import SubEntity


class CollectionDefinition(BaseModel):
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

    entities: Sequence[SubEntity] = Field(
        description="The sub-entity instances that this collection is to instantiate",
        default=(),
    )
