"""
A few global definitions
"""

from pydantic import BaseModel, ConfigDict


class BaseSettings(BaseModel):
    """A Base class for setting consistent Pydantic model configuration"""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
    )
