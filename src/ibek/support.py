"""
Support Class to represent a deserialized <MODULE_NAME>.ibek.support.yaml file.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from pydantic import Field

from .definition import EntityDefinition
from .globals import BaseSettings


class Support(BaseSettings):
    """
    Lists the definitions for a support module, this defines what Entities it supports

    Provides the deserialize entry point.
    """

    shared: Sequence[Any] = Field(
        description="A place to create any anchors required for repeating YAML",
        default=(),
    )

    module: str = Field(description="Support module name, normally the repo name")
    defs: Sequence[EntityDefinition] = Field(
        description="The definitions an IOC can create using this module"
    )

    @classmethod
    def get_schema(cls):
        return json.dumps(cls.model_json_schema(), indent=2)
