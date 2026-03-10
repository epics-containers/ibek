import errno
import json
import logging
import socket
import time
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

DOWAIT_DONE_FILE = Path("/tmp") / "doWait_completed.txt"
"""Used by other processes to check if the `do_wait` command has completed successfully and proceed accordingly."""


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


# Transient errno values that mean the remote end is not up yet but may become
# available.  These are re-raised as TimeoutError so the do_wait retry loops
# continue rather than exiting immediately.
_RETRYABLE_ERRNOS = {
    errno.ECONNREFUSED,  # port not open yet – most common when device hasn't started listening on the port yet
    errno.ENETUNREACH,  # network path not ready yet
    errno.EHOSTUNREACH,  # host not reachable yet (ARP / routing not settled)
    errno.ECONNRESET,  # connection reset during handshake
    errno.ENETDOWN,  # network interface not yet up
}


def try_connect(device: str, ip: str, port: int, timeout: float | None) -> None:
    """
    Attempt to connect to the given IP address and port using a socket with a timeout.
    If the connection is successful, the socket is closed and the function returns.

    :param device: The name of the device being connected to (used for logging).
    :param ip: The IP address to connect to.
    :param port: The port number to connect to.
    :param timeout: The timeout duration in seconds for the connection attempt. If None, wait indefinitely until a connection can be made.

    :raises TimeoutError: If the connection attempt times out *or* if a transient
        network error occurs (e.g. ECONNREFUSED, ENETUNREACH, EHOSTUNREACH)
        so that the caller's retry loop can keep waiting rather than giving up.
    :raises typer.Exit: If a non-retryable error occurs (e.g. invalid address
        family, bad file descriptor, permission denied).
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        try:
            client.connect((ip, port))
        except TimeoutError:
            raise
        except OSError as e:
            if e.errno in _RETRYABLE_ERRNOS:
                log.debug(
                    f"Transient error connecting to {device} at {ip}:{port} "
                    f"(errno {e.errno}: {e.strerror}); will retry"
                )
                raise TimeoutError(str(e)) from e
            log.error(f"Error connecting to {device} at {ip}:{port}: {e}")
            raise typer.Exit(1) from e


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
    # Ensure the done file is removed before starting the wait command (i.e. reset the state)
    if DOWAIT_DONE_FILE.exists():
        DOWAIT_DONE_FILE.unlink()

    if source.exists():
        yaml = YAML()
        wait_list = yaml.load(source) or []

        for entry in wait_list:
            if entry["type"] == "ibek.wait_ip":
                # Parse address into ip and port, defaulting port to 1025 if not specified.
                if ":" in entry["address"]:
                    ip, port = entry["address"].rsplit(":", 1)
                else:
                    log.warning(
                        f"Address '{entry['address']}' does not include a port number. "
                        f"It should be in the format 'ip:port'. Using port 1025 as default."
                    )
                    ip, port = entry["address"], "1025"

                timeout = entry["timeout"] if entry["timeout"] > 0 else None

                # Attempt to connect to the IP address and port using a socket with a timeout.
                # However, the system network stack may also return a connection timeout error of its own
                # regardless of any Python socket timeout setting; thus custom handling of the timeout is necessary.
                # (see 'Notes on socket timeouts' at https://docs.python.org/3/library/socket.html)

                # If the timeout is set to None, wait indefinitely until a connection can be made.
                if timeout is None:
                    typer.echo(
                        f"Waiting indefinitely for {entry['device']} at {entry['address']} to respond..."
                    )
                    while True:
                        try:
                            try_connect(entry["device"], ip, int(port), None)
                            break
                        except TimeoutError:
                            pass

                # If the timeout is set to a positive number, wait up to that many seconds for a connection to be made
                # before giving up and exiting with an error.
                else:
                    typer.echo(
                        f"Waiting up to {timeout} seconds for {entry['device']} at {entry['address']} to respond..."
                    )
                    end_time = time.time() + timeout
                    while time.time() < end_time:
                        try:
                            try_connect(
                                entry["device"], ip, int(port), end_time - time.time()
                            )
                            break
                        except TimeoutError:
                            pass
                    else:
                        typer.echo(
                            f"Connection to {entry['device']} at {entry['address']} timed out after {timeout} seconds",
                            err=True,
                        )
                        raise typer.Exit(1)

            else:
                # In the future, support for other types of wait commands could be added by defining additional entity models.
                # For example, waiting for a USB device to be present could be implemented
                # by checking for the device ID in the output of a command like `lsusb`
                # or by monitoring the `/dev` directory for the appearance of a device file corresponding to the USB device.
                typer.echo(
                    f"Wait entry type not supported yet: {entry['type']}", err=True
                )

        # Successfully got through the wait list without any connection timeouts or errors
        typer.echo("All 'wait' commands completed successfully.")

    else:
        typer.echo(f"No wait list file found at {source}, skipping wait commands.")

    # Create the done file to signal to other processes that the wait command is complete.
    # This is valid whether or not there was a wait list to process.
    DOWAIT_DONE_FILE.touch()
