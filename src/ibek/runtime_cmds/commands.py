import shutil
from pathlib import Path

import typer
from pvi._format.base import IndexEntry
from pvi._format.dls import DLSFormatter
from pvi._format.template import format_template
from pvi.device import Device, DeviceRef

from ibek.entity_factory import EntityFactory
from ibek.entity_model import Database
from ibek.gen_scripts import create_boot_script, create_db_script
from ibek.globals import GLOBALS, NaturalOrderGroup
from ibek.ibek_builtin.wait import DoWaitEntity
from ibek.ioc import IOC, BuiltInEntity, Entity
from ibek.ioc_factory import IocFactory
from ibek.runtime_cmds.autosave import AutosaveGenerator, link_req_files
from ibek.utils import UTILS

runtime_cli = typer.Typer(cls=NaturalOrderGroup)


@runtime_cli.command()
def generate2(
    config_folder: Path = typer.Argument(
        None,
        help="The IOC instance folder containing entity yaml files",
        exists=True,
        dir_okay=True,
        file_okay=False,
        autocompletion=lambda: [],
    ),
    instance_files: list[Path] = typer.Option(
        [],
        "--instance",
        "-i",
        help="Additional IOC instance entity yaml files",
        exists=True,
        dir_okay=False,
        file_okay=True,
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
    definitions: list[Path] = typer.Option(
        [],
        help="The filepath to a support module yaml file",
        exists=True,
        dir_okay=False,
        file_okay=True,
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
    output_folder: Path = typer.Option(
        GLOBALS.RUNTIME_OUTPUT,
        "--output",
        "-o",
        help="The folder to write the generated runtime files to",
    ),
    pvi: bool = typer.Option(True, help="generate pvi PVs and opi files"),
):
    """
    An updated version of generate that supports multiple instance files.
    This allows a main ioc.yaml with entities from the generic IOC image and
    additional runtime.yaml with entities from the services repository.
    """

    if not instance_files and not config_folder:
        typer.echo(
            "Error: Either instance folder or instance files must be provided.",
            err=True,
        )
        raise typer.Exit(code=1)

    if config_folder is not None:
        # Gather all yaml files in the instance folder
        for yaml_file in "ioc.yaml", "runtime.yaml":
            p = config_folder / yaml_file
            if (p).exists():
                instance_files.append(p)

    if len(instance_files) == 0:
        typer.echo("Error: No instance yaml files found.", err=True)
        raise typer.Exit(code=1)

    if len(definitions) == 0:
        # get definitions from the default locations
        definitions += Path(GLOBALS.IBEK_DEFS).glob("**/*ibek.support.yaml")
        definitions += config_folder.glob(
            "**/*.ibek.support.yaml", recurse_symlinks=True
        )

    do_generate(instance_files, definitions, output_folder, pvi)


@runtime_cli.command()
def generate(
    instance: Path = typer.Argument(
        ...,
        help="The filepath to the ioc instance entity file",
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
    definitions: list[Path] = typer.Argument(
        ...,
        help="The filepath to a support module yaml file",
        autocompletion=lambda: [],  # Forces path autocompletion
    ),
    output_folder: Path = typer.Option(
        GLOBALS.RUNTIME_OUTPUT,
        "--output",
        "-o",
        help="The folder to write the generated runtime files to",
    ),
    pvi: bool = typer.Option(True, help="generate pvi PVs and opi files"),
):
    do_generate([instance], definitions, output_folder, pvi)


def do_generate(
    instance_yamls: list[Path],
    definitions: list[Path],
    output_folder: Path,
    pvi: bool = True,
):
    """
    Build a startup script for an IOC instance

    Args:
        instance_yamls: List of filepaths to IOC instance entity files,
                        the first of which provides the IOC name
        definitions: List of filepaths to support module entity model definition files
        output_folder: Folder to write generated runtime files to
        pvi: Whether to generate pvi files and databases
    """
    # the file name under of the instance definition provides the IOC name
    UTILS.set_file_name(instance_yamls[0])

    entity_factory = EntityFactory()
    entity_models = entity_factory.make_entity_models(definitions)
    ioc_instance = IocFactory().deserialize_ioc(instance_yamls[0], entity_models)
    if len(instance_yamls) > 1:
        for yaml in instance_yamls[1:]:
            instance = IocFactory().deserialize_ioc(yaml, entity_models)
            ioc_instance.entities.extend(instance.entities)

    # post processing to insert SubEntity instances
    all_entities = entity_factory.resolve_sub_entities(ioc_instance.entities, {})

    # Clear out generated files so developers know if something stops being generated
    shutil.rmtree(output_folder, ignore_errors=True)
    output_folder.mkdir(exist_ok=True)

    # Separate built in entities and filter out any non-entity objects
    # that may be present in the list after processing (e.g. from SubEntity resolution)
    builtin_entities: list[BuiltInEntity] = []
    discrete_entities: list[Entity] = []
    for entity in all_entities:
        if isinstance(entity, BuiltInEntity):
            builtin_entities.append(entity)
        if not hasattr(entity, "_model"):
            continue
        discrete_entities.append(entity)
    ioc_instance.entities = discrete_entities

    for entity in builtin_entities:
        # Generate the wait for hardware file for the IOC instance.
        if isinstance(entity, DoWaitEntity):
            entity._process_entity(output_folder)

    # Generate pvi files and collect database information for entities with pvi definitions.
    pvi_databases: list = []
    if pvi:
        shutil.rmtree(GLOBALS.OPI_OUTPUT, ignore_errors=True)
        GLOBALS.OPI_OUTPUT.mkdir(exist_ok=True)

        pvi_index_entries, pvi_databases = generate_pvi(ioc_instance)
        generate_index(ioc_instance.ioc_name, pvi_index_entries)

    # Generate the boot script for the IOC instance.
    script_txt = create_boot_script(ioc_instance.entities)
    script_output = output_folder / "st.cmd"
    script_output.parent.mkdir(parents=True, exist_ok=True)
    with script_output.open("w") as stream:
        stream.write(script_txt)

    # Generate the database substitution file, including any generated pvi databases.
    db_txt = create_db_script(ioc_instance.entities, pvi_databases)
    db_output = output_folder / "ioc.subst"
    with db_output.open("w") as stream:
        stream.write(db_txt)


def _entity_hierarchy(entities: list[Entity], parent: Entity | None = None):
    for entity in entities:
        yield entity, parent
        for child in getattr(entity, "_child_entities", []):
            yield from _entity_hierarchy([child], entity)


def _nearest_pvi_device_ancestor(
    entity: Entity,
    entity_to_device: dict[int, Device],
    parent_map: dict[int, Entity | None],
) -> Device | None:
    while entity is not None:
        device = entity_to_device.get(id(entity))
        if device is not None:
            return device
        entity = parent_map.get(id(entity))
    return None


def generate_pvi(ioc: IOC) -> tuple[list[IndexEntry], list[tuple[Database, Entity]]]:
    """Generate pvi bob and template files to add to UI index and IOC database.

    Args:
        ioc: IOC instance to extract entity pvi definitions from

    Returns:
        List of bob files to add as buttons on index and databases to add to IOC
        substitution file

    """
    index_entries: list[IndexEntry] = []
    databases: list[tuple[Database, Entity]] = []

    formatter = DLSFormatter()
    parent_map: dict[int, Entity | None] = {}
    entity_to_device: dict[int, Device] = {}
    device_name_map: dict[str, Device] = {}

    for entity, parent in _entity_hierarchy(ioc.entities):
        parent_map[id(entity)] = parent  # Map allows us to reach upwards for ancestors
        definition = entity._model
        if not hasattr(definition, "pvi") or definition.pvi is None:
            continue
        entity_pvi = definition.pvi

        pvi_yaml = GLOBALS.PVI_DEFS / UTILS.render(entity, entity_pvi.yaml_path)
        device_name = pvi_yaml.name.split(".")[0]

        if device_name not in device_name_map:
            device = Device.deserialize(pvi_yaml)
            device.deserialize_parents([GLOBALS.PVI_DEFS])
            device_name_map[device_name] = device
        else:
            device = device_name_map[device_name]

        entity_to_device[id(entity)] = device
        if entity_pvi.pv:
            output_template = GLOBALS.RUNTIME_OUTPUT / f"{device_name}.pvi.template"
            format_template(device, entity_pvi.pv_prefix, output_template)
            databases.append(
                (
                    Database(file=output_template.name, args=entity_pvi.ui_macros),
                    entity,
                )
            )

        device_bob = GLOBALS.OPI_OUTPUT / f"{device_name}.pvi.bob"

        if parent is None and entity_pvi.ui_index:
            macros = UTILS.render_map(dict(entity), entity_pvi.ui_macros or {})
            index_entries.append(
                IndexEntry(
                    label=f"{device.label}",
                    ui=device_bob.name,
                    macros=macros,
                )
            )

        if parent is not None:
            # Find the nearest ancestor that has a pvi
            parent_device = _nearest_pvi_device_ancestor(
                parent, entity_to_device, parent_map
            )
            macros = UTILS.render_map(dict(entity), entity_pvi.ui_macros or {})
            # Insert sub devices into the ancestor
            if parent_device is not None:
                parent_device.children.append(
                    DeviceRef(
                        name=definition.name
                        if not getattr(entity, "_repeat_value", None)
                        else f"{parent_device.label}{entity._repeat_value}",
                        pv=UTILS.render(entity, entity_pvi.pv_prefix or ""),
                        ui=device_bob.name,
                        macros=macros,
                    )
                )
            # No ancestor has a pvi, so place in index
            else:
                index_entries.append(
                    IndexEntry(
                        label=f"{device.label}",
                        ui=device_bob.name,
                        macros=macros,
                    )
                )

    for device_name, device in device_name_map.items():
        device.merge_components(device.children)
        device_bob = GLOBALS.OPI_OUTPUT / f"{device_name}.pvi.bob"
        formatter.format(device, device_bob)

    return index_entries, databases


def generate_index(title: str, index_entries: list[IndexEntry]):
    """Generate an index bob using pvi.

    Args:
        title: Title of index UI
        index_entries: List of entries to include as buttons on index UI

    """
    DLSFormatter().format_index(title, index_entries, GLOBALS.OPI_OUTPUT / "index.bob")


@runtime_cli.command()
def generate_autosave(subst_file: Path = typer.Argument(GLOBALS.RUNTIME_SUBSTITUTION)):
    """
    Generate autosave request files from autosave settings and positions
    template files found in support module db folders. Allow overrides
    from ibek-support/* and /epics/ioc/config folders.

    CONVENTION: req template files must be in the support module db folder after
    the module is built. The template files must be named with the same stem
    as the db file that defines the PVs to be saved. The naming convention is:

    DbTemplateFileStem_positions.req : for autosave stage 0 settings
    DbTemplateFileStem_settings.req : for autosave stage 1 settings

    The steps are:
    1. at build time "ibek support generate-links" creates symlinks to override
       req files in /epics/autosave. These override req files come from individual
       ibek-support folders
    2. at runtime "ibek runtime generate-autosave" handles the remaining steps:
    3. All req files in /epics/support/*/db/ are symlinked to /epics/autosave
       except if that req file name already exists (from 1.)
    4. All req files in /epics/ioc/config are symlinked to /epics/autosave
       overwriting any existing req file (thus supplying instance overrides)
    5. AutosaveGenerator generates two substitution files for settings and positions.
       These substitution files are the same as ioc.db except that they contain
       the file names of the req templates instead of the db files. If ioc.db
       contains a database template that has no corresponding req template, then
       that line is omitted from the new substitution file.
    6. Two req files are generated from the two substitution files using MSI.

    Where the database template has a full path, this will be stripped in
    substitution files created in step 5. At runtime autosave will be pointed at
    the /epics/autosave folder for its search path. There is an issue with name
    collisions that we will address if this ever arises.
    """
    link_req_files()
    asg = AutosaveGenerator(subst_file)
    asg.generate_req_files()
