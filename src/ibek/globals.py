"""
A few global definitions
"""

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.core import TyperGroup

DEFAULT_ARCH = "linux-x86_64"


class _Globals:
    """Helper class for accessing global constants."""

    def __init__(self) -> None:
        self.EPICS_ROOT = Path(os.getenv("EPICS_ROOT", "/epics/"))
        """Root of epics directory tree.

        This can be overriden by defining an environment variable "EPICS_ROOT".
        """

        self.IBEK_DEFS = self.EPICS_ROOT / "ibek-defs"
        """Directory containing ibek support yaml definitions."""

        self.PVI_DEFS = self.EPICS_ROOT / "pvi-defs"
        """Directory containing pvi device yaml definitions."""

        self.RUNTIME_OUTPUT = self.EPICS_ROOT / "runtime"
        """Directory containing runtime generated assets for IOC boot."""

        self.OPI_OUTPUT = self.EPICS_ROOT / "opi"
        """Directory containing runtime generated opis to serve over http."""

        self.EPICS_TARGET_ARCH = os.getenv("EPICS_TARGET_ARCH", DEFAULT_ARCH)
        """The target architecture for the current container."""

        self.EPICS_HOST_ARCH = os.getenv("EPICS_HOST_ARCH", DEFAULT_ARCH)
        """The host architecture for the current container."""

        self.NATIVE = self.EPICS_TARGET_ARCH == self.EPICS_HOST_ARCH
        """True if the target architecture is the same as the host architecture."""

        default_static: bool = self.EPICS_TARGET_ARCH != DEFAULT_ARCH
        self.STATIC_BUILD = os.getenv("STATIC_BUILD", default_static)


GLOBALS = _Globals()

# TODO: Include all constants in _Globals

# get the container paths from environment variables
EPICS_BASE = Path(os.getenv("EPICS_BASE", "/epics/epics-base"))
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

# Paths for ibek-support
IBEK_GLOBALS = Path("_global")
SUPPORT_YAML_PATTERN = "*ibek.support.yaml"
PVI_YAML_PATTERN = "*pvi.device.yaml"

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
