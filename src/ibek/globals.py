"""
A few global definitions
"""

import os
from pathlib import Path
from typing import Dict

from jinja2 import Template
from pydantic import BaseModel, ConfigDict

from .utils import UTILS

# note requirement for environment variable EPICS_BASE
EPICS_BASE = Path(str(os.getenv("EPICS_BASE")))
EPICS_ROOT = Path(str(os.getenv("EPICS_ROOT")))

# all support modules will reside under this directory
SUPPORT = Path(str(os.getenv("SUPPORT")))
# the global RELEASE file which lists all support modules
RELEASE = Path(f"{SUPPORT}/configure/RELEASE")
# a bash script to export the macros defined in RELEASE as environment vars
RELEASE_SH = Path(f"{SUPPORT}/configure/RELEASE.shell")
# global MODULES file used to determine order of build
MODULES = Path(f"{SUPPORT}/configure/MODULES")
# Folder containing Makefile.jinja
MAKE_FOLDER = Path(str(os.getenv("IOC"))) / "iocApp/src"
# Folder containing ibek support scripts
SCRIPTS_FOLDER = Path("/workspaces/ibek-support")


class BaseSettings(BaseModel):
    """A Base class for setting consistent Pydantic model configuration"""

    model_config = ConfigDict(
        extra="forbid",
    )


def render_with_utils(context: Dict, template_text: str) -> str:
    """
    Render a Jinja template with the global __utils__ object in the context
    """
    jinja_template = Template(template_text)
    return jinja_template.render(context, __utils__=UTILS)
