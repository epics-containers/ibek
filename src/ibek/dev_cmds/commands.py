import logging
import shutil
from pathlib import Path

import typer

from ibek.globals import GLOBALS, NaturalOrderGroup

log = logging.getLogger(__name__)
dev_cli = typer.Typer(cls=NaturalOrderGroup)


@dev_cli.command()
def instance(
    instance: Path = typer.Argument(
        ...,
        help="The filepath to the ioc instance entity file",
        dir_okay=True,
        file_okay=False,
        exists=True,
        autocompletion=lambda: [],  # Forces path autocompletion
        resolve_path=True,
    ),
):
    """
    Symlink an IOC instance config folder into /epics/ioc/config.

    Used in the devcontainer to allow the IOC instance to be run using
    /epics/ioc/starts.sh. Changes made to the config will be immediately
    available and also under version control.

    e.g. if instance is /workspaces/bl38p/iocs/bl38p-mo-panda-01 then we need:
    - /epics/ioc/config -> /workspaces/bl38p/iocs/bl38p-mo-panda-01/config
    """

    # validate the instance folder has a config folder
    ioc_folder = GLOBALS.IOC_FOLDER
    config_folder = ioc_folder / GLOBALS.CONFIG_DIR_NAME
    instance_config = instance / GLOBALS.CONFIG_DIR_NAME

    # verify that the expected folder exists
    if not ioc_folder.exists():
        log.error(f"Could not find ioc folder {ioc_folder}")
        raise typer.Exit(1)

    # remove any existing config folder from /epics/ioc
    if config_folder.is_symlink():
        config_folder.unlink()
    elif config_folder.exists():
        shutil.rmtree(config_folder)

    # Now symlink the instance config folder into /epics/ioc
    print(f"Symlinking {instance_config} to {config_folder}")
    config_folder.symlink_to(instance_config)


@dev_cli.command()
def support(
    module: Path = typer.Argument(
        ...,
        help="The filepath to the support module to work on",
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
):
    """
    enable a support module for development.
    """

    raise NotImplementedError
