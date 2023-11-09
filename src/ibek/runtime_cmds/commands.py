import shutil
from pathlib import Path
from typing import List, Tuple

import typer
from pvi._format.base import IndexEntry
from pvi._format.dls import DLSFormatter
from pvi._format.template import format_template
from pvi.device import Device

from ibek.gen_scripts import create_boot_script, create_db_script, ioc_deserialize
from ibek.globals import (
    OPI_OUTPUT_PATH,
    PVI_DEFS,
    RUNTIME_OUTPUT_PATH,
    NaturalOrderGroup,
)
from ibek.ioc import IOC, Entity
from ibek.support import Database

runtime_cli = typer.Typer(cls=NaturalOrderGroup)

PVI_PV_PREFIX = "${prefix}"


@runtime_cli.command()
def generate(
    instance: Path = typer.Argument(
        ..., help="The filepath to the ioc instance entity file"
    ),
    definitions: List[Path] = typer.Argument(
        ..., help="The filepath to a support module definition file"
    ),
    out: Path = typer.Option(
        default=RUNTIME_OUTPUT_PATH / "st.cmd",
        help="Path to output startup script",
    ),
    db_out: Path = typer.Option(
        default=RUNTIME_OUTPUT_PATH / "ioc.subst",
        help="Path to output database expansion shell script",
    ),
):
    """
    Build a startup script for an IOC instance
    """
    ioc_instance = ioc_deserialize(instance, definitions)

    # Clear out generated files so developers know if something stop being generated
    shutil.rmtree(RUNTIME_OUTPUT_PATH, ignore_errors=True)
    RUNTIME_OUTPUT_PATH.mkdir(exist_ok=True)
    shutil.rmtree(OPI_OUTPUT_PATH, ignore_errors=True)
    OPI_OUTPUT_PATH.mkdir(exist_ok=True)

    pvi_index_entries, pvi_databases = generate_pvi(ioc_instance)
    generate_index(ioc_instance.ioc_name, pvi_index_entries)

    script_txt = create_boot_script(ioc_instance)

    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w") as stream:
        stream.write(script_txt)

    db_txt = create_db_script(ioc_instance, pvi_databases)

    with db_out.open("w") as stream:
        stream.write(db_txt)


def generate_pvi(ioc: IOC) -> Tuple[List[IndexEntry], List[Tuple[Database, Entity]]]:
    """Generate pvi bob and template files to add to UI index and IOC database.

    Args:
        ioc: IOC instance to extract entity pvi definitions from

    Returns:
        List of bob files to add as buttons on index and databases to add to IOC
        substitution file

    """
    index_entries: List[IndexEntry] = []
    databases: List[Tuple[Database, Entity]] = []

    formatter = DLSFormatter()

    formatted_pvi_devices: List[str] = []
    for entity in ioc.entities:
        entity_pvi = entity.__definition__.pvi
        if entity_pvi is None:
            continue

        pvi_yaml = PVI_DEFS / entity_pvi.yaml_path
        device_name = pvi_yaml.name.split(".")[0]
        device_bob = OPI_OUTPUT_PATH / f"{device_name}.pvi.bob"

        # Skip deserializing yaml if not needed
        if entity_pvi.pva or device_name not in formatted_pvi_devices:
            device = Device.deserialize(pvi_yaml)
            device.deserialize_parents([PVI_DEFS])

            macros = {"prefix": entity_pvi.prefix}

            if entity_pvi.pva:
                # Create a template with the V4 structure defining a PVI interface
                output_template = RUNTIME_OUTPUT_PATH / f"{device_name}.pvi.template"
                format_template(device, PVI_PV_PREFIX, output_template)

                # Add to extra databases to be added into substitution file
                databases.append(
                    (Database(file=output_template.as_posix(), args=macros), entity)
                )

            if device_name not in formatted_pvi_devices:
                formatter.format(device, PVI_PV_PREFIX, device_bob)

                # Don't format further instance of this device
                formatted_pvi_devices.append(device_name)

        if entity_pvi.index:
            index_entries.append(IndexEntry(device_name, device_bob.name, macros))

    return index_entries, databases


def generate_index(title: str, index_entries: List[IndexEntry]):
    """Generate an index bob using pvi.

    Args:
        title: Title of index UI
        index_entries: List of entries to include as buttons on index UI

    """
    DLSFormatter().format_index(title, index_entries, OPI_OUTPUT_PATH / "index.bob")
