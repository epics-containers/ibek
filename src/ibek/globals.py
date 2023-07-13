"""
A few global definitions
"""

from pydantic import BaseModel, ConfigDict

# pydantic model configuration
model_config = ConfigDict(
    arbitrary_types_allowed=True,
    extra="forbid",
)


class BaseSettings(BaseModel):
    """A Base class for setting Pydantic model configuration"""

    model_config = model_config
