"""
A few global definitions
"""

from typing import Dict

from jinja2 import Template
from pydantic import BaseModel, ConfigDict

from .utils import UTILS


class BaseSettings(BaseModel):
    """A Base class for setting consistent Pydantic model configuration"""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
    )


def render_with_utils(context: Dict, template_text: str) -> str:
    """
    Render a Jinja template with the global __utils__ object available
    """
    jinja_template = Template(template_text)
    return jinja_template.render(context, __utils__=UTILS)
