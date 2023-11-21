import logging
import shutil
from pathlib import Path

import typer

from ibek.globals import CONFIG_DIR_NAME, IOC_DIR_NAME, IOC_FOLDER, NaturalOrderGroup
from ibek.ioc_cmds.assets import get_ioc_source

log = logging.getLogger(__name__)
dev_cli = typer.Typer(cls=NaturalOrderGroup)


@dev_cli.command()
def instance(
    instance: Path = typer.Argument(
        ..., help="The filepath to the ioc instance entity file"
    ),
):
    """
    Symlink an IOC instance config folder into /epics/ioc/config.

    Used in the devcontainer to allow the IOC instance to be run using
    /epics/ioc/starts.sh. Changes made to the config will be immediately
    available and also under version control.

    e.g. if instance is /repos/bl38p/iocs/bl38p-mo-panda-01 then we need:
    - /epics/ioc -> /epics/ioc-pandablocks/ioc
    - /epics/ioc/config -> /repos/bl38p/iocs/bl38p-mo-panda-01/config
    """
    # validate the instance folder has a config folder

    generic_root = get_ioc_source()
    ioc_folder = generic_root / IOC_DIR_NAME
    config_folder = ioc_folder / CONFIG_DIR_NAME
    instance_config = instance / CONFIG_DIR_NAME

    if not instance_config.exists():
        log.error(f"Could not find config folder {instance_config}")
        raise typer.Exit(1)

    # First make sure there is an ioc folder in the generic IOC source root
    # and that it is symlinked from /epics/ioc, remove any existing config.
    if not ioc_folder.exists():
        ioc_folder.mkdir()

    # remove any existing config folder and ioc symlink from /epics/ioc
    for folder in [config_folder, IOC_FOLDER]:
        if folder.is_symlink():
            folder.unlink()
        if folder.exists():
            shutil.rmtree(folder)

    IOC_FOLDER.symlink_to(ioc_folder)

    # Now symlink the instance config folder into the generic IOC source root
    config_folder.symlink_to(instance_config)


@dev_cli.command()
def support(
    module: Path = typer.Argument(
        ..., help="The filepath to the support module to work on"
    ),
):
    """
    enable a support module for development.
    """

    raise NotImplementedError
