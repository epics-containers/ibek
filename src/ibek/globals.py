"""
A few global definitions
"""

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.core import TyperGroup


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
    def RUNTIME_SUBSTITUTION(self):
        """Directory containing runtime generated assets for IOC boot."""
        return self.RUNTIME_OUTPUT / "ioc.subst"

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
    def AUTOSAVE(self):
        """Directory softlinks to all autosave req files."""
        return self._EPICS_ROOT / "autosave"

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
SUPPORT_YAML_PATTERN = "*ibek.support.yaml"
PVI_YAML_PATTERN = "*pvi.device.yaml"
AUTOSAVE_PATTERN = "*.req"

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
