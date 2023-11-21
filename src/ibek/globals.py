"""
A few global definitions
"""

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.core import TyperGroup

# get the container paths from environment variables
EPICS_BASE = Path(os.getenv("EPICS_BASE", "/epics/epics-base"))
EPICS_ROOT = Path(os.getenv("EPICS_ROOT", "/epics/"))
IOC_FOLDER = Path(os.getenv("IOC", "/epics/ioc"))
SUPPORT = Path(os.getenv("SUPPORT", "/epics/support"))
CONFIG_DIR_NAME = "config"
IOC_DIR_NAME = "ioc"

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

# Assets generated at runtime
RUNTIME_OUTPUT_PATH = EPICS_ROOT / "runtime"
OPI_OUTPUT_PATH = EPICS_ROOT / "opi"

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
