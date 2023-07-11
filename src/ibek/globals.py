"""
A few global definitions
"""
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field

#: A generic Type for use in type hints
T = TypeVar("T")


def desc(description: str):
    """a description Annotation to add to our Entity derived Types"""
    return Field(description=description)


class BaseSettings(BaseModel):
    """A Base class for setting Pydantic model configuration"""

    # Pydantic model configuration
    model_config = ConfigDict(
        # arbitrary_types_allowed=True,
        extra="forbid",
    )
