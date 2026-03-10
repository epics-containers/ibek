import json
import logging
import socket
from pathlib import Path
from typing import Annotated

import typer
from ruamel.yaml import YAML

from ibek.entity_factory import EntityFactory
from ibek.globals import (
    GLOBALS,
    SUPPORT_YAML_PATTERN,
    NaturalOrderGroup,
)
from ibek.ioc_cmds.docker import build_dockerfile
from ibek.ioc_factory import IocFactory

from .assets import extract_assets

log = logging.getLogger(__name__)
ioc_cli = typer.Typer(cls=NaturalOrderGroup)


@ioc_cli.command()
def build_docker(
    start: int = typer.Option(1, help="The step to start at in the Dockerfile"),
    stop: int = typer.Option(999, help="The step to stop at in the Dockerfile"),
    dockerfile: Annotated[
        Path,
        typer.Option(
            help="The filepath to the Dockerfile to build",
            autocompletion=lambda: [],  # Forces path autocompletion
        ),
    ] = Path.cwd() / "Dockerfile",
):
    """
    EXPERIMENTAL: Attempt to interpret the Dockerfile and run it's commands
    inside the devcontainer. For internal, incremental builds of the Dockerfile.

    Useful for debugging the Dockerfile without having to build the whole
    container from outside of the IOC devcontainer.
    """
    build_dockerfile(dockerfile, start, stop)


@ioc_cli.command()
def generate_schema(
    definitions: list[Path] = typer.Argument(
        None,  # Note: typer converts None to an empty list because the type is List
        help="File paths to one or more support module YAML files",
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
    output: Annotated[
        Path | None,
        typer.Option(
            help="The file path to the schema file to be written",
            autocompletion=lambda: [],  # Forces path autocompletion
        ),
    ] = None,
    ibek_defs: bool = typer.Option(
        True, help=f"Include definitions in {GLOBALS.IBEK_DEFS} in generated schema"
    ),
):
    """
    Create a json schema from a number of support_module.ibek.support.yaml
    files
    """
    if not (definitions or ibek_defs):
        log.error("One or more `definitions` required with `--no-ibek-defs`")
        raise typer.Exit(1)

    definitions = definitions or []

    if ibek_defs:
        # this allows us to use the definitions inside the container
        # which are in a known location after the container is built
        definitions += GLOBALS.IBEK_DEFS.glob(SUPPORT_YAML_PATTERN)

    if not definitions:
        log.error(f"No `definitions` given and none found in {GLOBALS.IBEK_DEFS}")
        raise typer.Exit(1)

    entity_factory = EntityFactory()
    entity_models = entity_factory.make_entity_models(definitions)
    ioc_factory = IocFactory()
    ioc_model = ioc_factory.make_ioc_model(entity_models)

    schema = json.dumps(ioc_model.model_json_schema(), indent=2)
    if output is None:
        typer.echo(schema)
    else:
        output.write_text(schema + "\n")


# TODO I believe this could be replaced by an ansible role too
@ioc_cli.command()
def extract_runtime_assets(
    destination: Path = typer.Argument(
        ...,
        help="The root folder to extract assets into",
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
    extras: list[Path] = typer.Argument(None, help="list of files to also extract"),
    source: Path = typer.Option(
        Path("/epics"),
        help="The root folder to extract assets from",
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
    defaults: bool = typer.Option(True, help="copy the default assets"),
    dry_run: bool = typer.Option(False, help="show what would happen"),
):
    """
    Find all the runtime assets in an EPICS installation and copy them to a
    new folder hierarchy for packaging into a container runtime stage.

    This should be performed in a throw away container stage (runtime_prep)
    as it is destructive of the source folder, because it uses move for speed.
    """
    extras = extras or []
    extract_assets(destination, source, extras, defaults, dry_run)


@ioc_cli.command()
def do_wait(
    source: Path = typer.Option(
        GLOBALS.RUNTIME_OUTPUT / "wait_list.yaml",
        help="The YAML file containing the list of wait commands to execute",
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
):
    """
    Read the YAML list file which includes the devices to wait for and execute the appropriate wait command for each device type.
    Currently only supports request to wait for successful connection to a remote socket.
    """
    if source.exists():
        yaml = YAML()
        wait_list = yaml.load(source) or []

        for entry in wait_list:
            if entry["type"] == "ibek.wait_ip":
                # Check that the port number is included in the address.
                if ":" not in entry["address"]:
                    log.warning(
                        f"Address '{entry['address']}' does not include a port number. "
                        f"It should be in the format 'ip:port'. Using port 1025 as default."
                    )

                # Attempt to connect to the IP address and port using a socket with a timeout.
                try:
                    log.info(
                        f"Waiting for {entry['device']} at {entry['address']} to respond..."
                    )
                    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    client.settimeout(
                        entry["timeout"] if entry["timeout"] > 0 else None
                    )
                    ip, port = (
                        entry["address"].split(":")
                        if ":" in entry["address"]
                        else (entry["address"], "1025")
                    )
                    client.connect((ip, int(port)))
                    client.close()
                    log.info(
                        f"Successfully connected to {entry['device']} at {entry['address']}."
                    )
                except TimeoutError:
                    log.error(
                        f"Connection to {entry['device']} at {entry['address']} timed out after {entry['timeout']} seconds"
                    )
                    exit(1)
                except OSError as e:
                    log.error(
                        f"Error connecting to {entry['device']} at {entry['address']}: {e}"
                    )
                    exit(1)

            else:
                # In the future, support for other types of wait commands could be added by defining additional entity models.
                # For example, waiting for a USB device to be present could be implemented
                # by checking for the device ID in the output of a command like `lsusb`
                # or by monitoring the `/dev` directory for the appearance of a device file corresponding to the USB device.
                log.warning(f"Wait entry type not supported yet: {entry['type']}")
