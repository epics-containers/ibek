"""
A few global definitions
"""

import os
from pathlib import Path
from typing import Dict

from jinja2 import Template
from pydantic import BaseModel, ConfigDict
from typer.core import TyperGroup

from .utils import UTILS

# get the container paths from environment variables
EPICS_BASE = Path(os.getenv("EPICS_BASE", "/epics/epics-base"))
EPICS_ROOT = Path(os.getenv("EPICS_ROOT", "/epics/"))
IOC_FOLDER = Path(os.getenv("IOC", "/epics/ioc"))
SUPPORT = Path(os.getenv("SUPPORT", "/epics/support"))

# the global RELEASE file which lists all support modules
RELEASE = SUPPORT / "configure/RELEASE"
# a bash script to export the macros defined in RELEASE as environment vars
RELEASE_SH = SUPPORT / "configure/RELEASE.shell"
# global MODULES file used to determine order of build
MODULES = SUPPORT / "configure/MODULES"

# Folder containing templates for IOC src etc.
TEMPLATES = Path(__file__).parent / "templates"

# Definitions populated at container build time
IBEK_DEFS = EPICS_ROOT / "ibek-defs"
PVI_DEFS = EPICS_ROOT / "pvi-defs"

# Paths for ibek-support
IBEK_SUPPORT = Path("ibek-support")
IBEK_GLOBALS = Path("_global")
SUPPORT_YAML_PATTERN = "*ibek.support.yaml"
PVI_YAML_PATTERN = "*pvi.device.yaml"

# UIs and templates generated at runtime
OPI_OUTPUT_PATH = EPICS_ROOT / "opi"
RUNTIME_OUTPUT_PATH = EPICS_ROOT / "runtime"

IOC_DBDS = SUPPORT / "configure/dbd_list"
IOC_LIBS = SUPPORT / "configure/lib_list"
RUNTIME_DEBS = SUPPORT / "configure/runtime_debs"


class BaseSettings(BaseModel):
    """A Base class for setting consistent Pydantic model configuration"""

    model_config = ConfigDict(
        extra="forbid",
    )


class NaturalOrderGroup(TyperGroup):
    def list_commands(self, ctx):
        return self.commands.keys()


def render_with_utils(context: Dict, template_text: str) -> str:
    """
    Render a Jinja template with the global __utils__ object in the context
    """
    jinja_template = Template(template_text)
    return jinja_template.render(context, __utils__=UTILS)
