"""
A few global definitions
"""

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.core import TyperGroup

DEFAULT_ARCH = "linux-x86_64"


class _Globals:
    """
    Helper class for accessing global constants.

    These constants define the paths to the various directories used by the
    ibek commands.
    """

    def __init__(self) -> None:
        """Initialize the global constants."""

        # Can be overridden by defining an environment variable "EPICS_ROOT"
        self._EPICS_ROOT = Path(os.getenv("EPICS_ROOT", "/epics/"))

        self._DEFAULT_ARCH = "linux-x86_64"

    @property
    def EPICS_ROOT(self):
        """Root of epics directory tree"""
        return self._EPICS_ROOT

    @property
    def SUPPORT(self):
        """Directory containing support module clones"""
        return self._EPICS_ROOT / "support"

    @property
    def RELEASE(self):
        """The global RELEASE file which lists all support modules"""
        return self._EPICS_ROOT / "support" / "configure" / "RELEASE"

    @property
    def RUNTIME_OUTPUT(self):
        """Directory containing runtime generated assets for IOC boot."""
        return self._EPICS_ROOT / "runtime"

    @property
    def EPICS_TARGET_ARCH(self):
        """The target architecture for the current container."""
        return os.getenv("EPICS_TARGET_ARCH", self._DEFAULT_ARCH)

    @property
    def EPICS_HOST_ARCH(self):
        """The host architecture for the current container."""
        return os.getenv("EPICS_HOST_ARCH", self._DEFAULT_ARCH)

    @property
    def NATIVE(self):
        """True if the target architecture is the same as the host architecture."""
        return self.EPICS_TARGET_ARCH == self.EPICS_HOST_ARCH

    @property
    def STATIC_BUILD(self):
        """True if the target architecture is not the default architecture."""
        return os.getenv("STATIC_BUILD", self.EPICS_TARGET_ARCH != self._DEFAULT_ARCH)

    @property
    def IBEK_DEFS(self):
        """Directory containing ibek support yaml files."""
        return self._EPICS_ROOT / "ibek-defs"

    @property
    def PVI_DEFS(self):
        """Directory containing pvi device yaml files."""
        return self._EPICS_ROOT / "pvi-defs"

    @property
    def OPI_OUTPUT(self):
        """Directory containing runtime generated opis to serve over http."""
        return self._EPICS_ROOT / "opi"

    @property
    def EPICS_BASE(self):
        """The folder containing the epics base source and binaries"""
        return self._EPICS_ROOT / "epics-base"

    @property
    def IOC_FOLDER(self):
        """root folder of a generic IOC source inside the container"""
        return self._EPICS_ROOT / "ioc"

    @property
    def CONFIG_DIR_NAME(self):
        """Name of config directory within IOC directory"""
        return "config"

    @property
    def IOC_DIR_NAME(self):
        """folder of the IOC source"""
        return "ioc"

    @property
    def RELEASE_SH(self):
        """a bash script to export the macros defined in RELEASE as environment vars"""
        return self.SUPPORT / "configure" / "RELEASE.shell"

    @property
    def MODULES(self):
        """global MODULES file used to determine order of build"""
        return self.SUPPORT / "configure" / "MODULES"

    @property
    def IOC_DBDS(self):
        """ibek-support list of declared dbds"""
        return self.SUPPORT / "configure" / "dbd_list"

    @property
    def IOC_LIBS(self):
        """ibek-support list of declared libs"""
        return self.SUPPORT / "configure" / "lib_list"

    @property
    def RUNTIME_DEBS(self):
        """ibek-support list of declared deb packages to install in runtime stage"""
        return self.SUPPORT / "configure" / "runtime_debs"

    @property
    def RUNTIME_FILES(self):
        """ibek-support list of files to copy to the runtime stage"""
        return self.SUPPORT / "configure" / "runtime_files_list"


# Folder containing templates for IOC src etc.
TEMPLATES = Path(__file__).parent / "templates"

# Path suffixes for ibek-support
IBEK_GLOBALS = Path("_global")
SUPPORT_YAML_PATTERN = "*ibek.support.yaml"
PVI_YAML_PATTERN = "*pvi.device.yaml"

GLOBALS = _Globals()

JINJA = r".*\{\{.*\}\}.*"


class BaseSettings(BaseModel):
    """A Base class for setting consistent Pydantic model configuration"""

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
    )


class NaturalOrderGroup(TyperGroup):
    def list_commands(self, ctx):
        return self.commands.keys()
