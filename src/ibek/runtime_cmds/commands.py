import shutil
from pathlib import Path
from typing import List, Tuple

import typer
from pvi._format.base import IndexEntry
from pvi._format.dls import DLSFormatter
from pvi._format.template import format_template
from pvi.device import Device

from ibek.entity_factory import EntityFactory
from ibek.entity_model import Database
from ibek.gen_scripts import create_boot_script, create_db_script
from ibek.globals import GLOBALS, NaturalOrderGroup
from ibek.ioc import IOC, Entity
from ibek.ioc_factory import IocFactory
from ibek.utils import UTILS

runtime_cli = typer.Typer(cls=NaturalOrderGroup)


@runtime_cli.command()
def generate(
    instance: Path = typer.Argument(
        ...,
        help="The filepath to the ioc instance entity file",
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
    definitions: List[Path] = typer.Argument(
        ...,
        help="The filepath to a support module yaml file",
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
):
    """
    Build a startup script for an IOC instance
    """
    # the file name under of the instance definition provides the IOC name
    UTILS.set_file_name(instance)

    entity_factory = EntityFactory()
    entity_models = entity_factory.make_entity_models(definitions)
    ioc_instance = IocFactory().deserialize_ioc(instance, entity_models)

    # post processing to insert SubEntity instances
    all_entities = entity_factory.resolve_sub_entities(ioc_instance.entities)
    ioc_instance.entities = all_entities

    # Clear out generated files so developers know if something stops being generated
    shutil.rmtree(GLOBALS.RUNTIME_OUTPUT, ignore_errors=True)
    GLOBALS.RUNTIME_OUTPUT.mkdir(exist_ok=True)
    shutil.rmtree(GLOBALS.OPI_OUTPUT, ignore_errors=True)
    GLOBALS.OPI_OUTPUT.mkdir(exist_ok=True)

    pvi_index_entries, pvi_databases = generate_pvi(ioc_instance)
    generate_index(ioc_instance.ioc_name, pvi_index_entries)

    script_txt = create_boot_script(ioc_instance.entities)
    script_output = GLOBALS.RUNTIME_OUTPUT / "st.cmd"
    script_output.parent.mkdir(parents=True, exist_ok=True)
    with script_output.open("w") as stream:
        stream.write(script_txt)

    db_txt = create_db_script(ioc_instance.entities, pvi_databases)
    db_output = GLOBALS.RUNTIME_OUTPUT / "ioc.subst"
    with db_output.open("w") as stream:
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
        definition = entity._model
        if not hasattr(definition, "pvi") or definition.pvi is None:
            continue
        entity_pvi = definition.pvi

        pvi_yaml = GLOBALS.PVI_DEFS / UTILS.render(entity, entity_pvi.yaml_path)
        device_name = pvi_yaml.name.split(".")[0]
        device_bob = GLOBALS.OPI_OUTPUT / f"{device_name}.pvi.bob"

        # Skip deserializing yaml if not needed
        if entity_pvi.pv or device_name not in formatted_pvi_devices:
            device = Device.deserialize(pvi_yaml)
            device.deserialize_parents([GLOBALS.PVI_DEFS])

            if entity_pvi.pv:
                # Create a template with the V4 structure defining a PVI interface
                output_template = GLOBALS.RUNTIME_OUTPUT / f"{device_name}.pvi.template"
                format_template(device, entity_pvi.pv_prefix, output_template)

                # Add to extra databases to be added into substitution file
                databases.append(
                    (
                        Database(file=output_template.name, args=entity_pvi.ui_macros),
                        entity,
                    )
                )

            if device_name not in formatted_pvi_devices:
                formatter.format(device, device_bob)

                # Don't format further instance of this device
                formatted_pvi_devices.append(device_name)

        if entity_pvi.ui_index:
            macros = UTILS.render_map(dict(entity), entity_pvi.ui_macros)
            index_entries.append(
                IndexEntry(
                    label=f"{device.label}",
                    ui=device_bob.name,
                    macros=macros,
                )
            )

    return index_entries, databases


def generate_index(title: str, index_entries: List[IndexEntry]):
    """Generate an index bob using pvi.

    Args:
        title: Title of index UI
        index_entries: List of entries to include as buttons on index UI

    """
    DLSFormatter().format_index(title, index_entries, GLOBALS.OPI_OUTPUT / "index.bob")
