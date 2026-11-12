"""
Support Class to represent a deserialized <MODULE_NAME>.ibek.support.yaml file.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import Field
from ruamel.yaml import YAML

from .entity_model import EntityModel
from .globals import BaseSettings


class Support(BaseSettings):
    """
    Lists the EntityModels for a support module, this defines what Entities it supports
    """

    shared: Sequence[Any] = Field(
        description="A place to create any anchors required for repeating YAML",
        default=(),
    )

    module: str = Field(description="Support module name, normally the repo name")
    entity_models: Sequence[EntityModel] = Field(
        description="The Entity Models an IOC can create using this module"
    )

    @classmethod
    def get_schema(cls):
        return json.dumps(cls.model_json_schema(), indent=2)


def support_yaml_module(path: Path) -> str | None:
    """The ``module`` a support YAML file declares, or None if it declares none.

    Reads only the top-level ``module`` key, without validating the rest of the
    file. Raises ``OSError`` or ``ruamel.yaml.error.YAMLError`` for a file that
    cannot be read or parsed.
    """
    data = YAML(typ="safe").load(path)
    if not isinstance(data, dict):
        return None
    module = data.get("module")
    if module is None:
        return None
    return str(module).strip() or None
