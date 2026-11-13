import logging
import shutil
from pathlib import Path

import typer

from ibek.globals import GLOBALS, NaturalOrderGroup

from . import clones, drift
from .stamp import (
    Stamp,
    StampError,
    compute,
    created_image_id_file,
    image_id_file,
    load,
    source,
    stamp_file,
    support_folder,
)

log = logging.getLogger(__name__)
dev_cli = typer.Typer(cls=NaturalOrderGroup)


def _image_id(path: Path) -> str:
    """The image ID in a file, or nothing if there is none to read."""
    try:
        return path.read_text().strip().removeprefix("sha256:")
    except (OSError, UnicodeDecodeError):
        return ""


def _warn_stale_container() -> None:
    """
    Say when the developer image on the host is not the one this container
    was created from. Says nothing unless both image IDs can be read.
    """
    created = _image_id(created_image_id_file())
    now = _image_id(image_id_file())
    if created and now and created != now:
        print(
            "WARNING: this container was created from a different developer "
            "image than the one now on this machine. Use "
            '"Dev Containers: Rebuild Container" in VS Code to move to it.',
            flush=True,
        )


def _state(strict: bool = False) -> tuple[Stamp, Stamp] | None:
    """
    Read the stamp and the live source tree.

    When there is nothing to compare, say why in one line and return None.
    With strict, a stamp or a source tree that cannot be read is an error.
    """
    try:
        made = load()
        if made is None:
            print(
                f"ibek dev: no {stamp_file()}: this image was built without "
                "`ibek dev stamp`, nothing to compare"
            )
            return None
        return made, compute()
    except StampError as error:
        if strict:
            raise _fail(error) from error
        print(f"ibek dev: {error}")
        return None


def _show(found: drift.Drift) -> None:
    lines = drift.report(found)
    if not lines:
        print(f"ibek dev: this container matches {source()}")
    else:
        print(f"ibek dev: this container differs from {source()}:")
    for line in lines:
        print(f"  {line}")
    for name, clone in found.clones.items():
        print(f"ibek dev: {name} is linked to its clone {clone}")


def _fail(message: object) -> typer.Exit:
    typer.echo(f"ibek dev: {message}", err=True)
    return typer.Exit(1)


@dev_cli.command()
def stamp():
    """
    Record the source tree that this image is built from.

    Run as the last step of the developer stage of a generic IOC Dockerfile,
    after copying Dockerfile and requirements.txt into /epics/generic-source.
    Writes /epics/dev-stamp.json, which the other dev commands compare with
    the host project that a devcontainer mounts over /epics/generic-source.
    """
    try:
        made = compute()
        made.save()
    except StampError as error:
        raise _fail(error) from error
    print(f"ibek dev: wrote {stamp_file()} for {len(made.modules)} support modules")


@dev_cli.command()
def status():
    """
    Show how this container differs from the mounted source. Changes nothing.
    """
    _warn_stale_container()
    state = _state()
    if state is not None:
        _show(drift.compare(*state))


@dev_cli.command()
def sync(
    build: bool = typer.Option(
        False,
        "--build",
        help="Also rebuild out of date support modules, those after them in "
        "the Dockerfile, and the IOC",
    ),
):
    """
    Bring this container level with the mounted source.

    Links changed support definition files, removes dangling links and
    regenerates the IOC schema. Everything that needs a build is reported and
    left alone unless --build is given.
    """
    _warn_stale_container()
    # with --build, a stamp or a source tree that cannot be read is an error:
    # nothing can be built. No stamp at all is one line and exit 0, as ever.
    state = _state(strict=build)
    if state is None:
        return
    made, live = state
    found = drift.compare(made, live)
    try:
        if build and found.requirements:
            requirements = source() / "requirements.txt"
            drift.run(["uv", "pip", "install", "--upgrade", "-r", str(requirements)])
            # the packages on disk are not the ones this process has loaded:
            # the schema comes from a fresh ibek, anything more from a fresh run.
            # The schema cannot be made while a definition link dangles.
            if found.defs or found.dangling:
                drift.fix_defs(made, live, found)
            else:
                drift.schema()
            made.requirements = live.requirements
            made.save()
            print(
                "ibek dev: upgraded the Python packages of requirements.txt. "
                "Run `ibek dev sync --build` again for anything more."
            )
            _show(drift.compare(made, live))
            # what the upgrade printed has pushed the warning out of sight
            _warn_stale_container()
            return
        if found.defs or found.dangling:
            drift.fix_defs(made, live, found)
        built = build and bool(found.rebuild or found.ioc)
        if built:
            drift.build(made, live, found)
    except StampError as error:
        raise _fail(error) from error
    _show(drift.compare(made, live))
    if built:
        # what the build printed has pushed the warning out of sight
        _warn_stale_container()


def _instance_report() -> None:
    """Report drift for someone about to run an instance. Never an error."""
    try:
        _warn_stale_container()
        state = _state()
        if state is not None:
            _show(drift.compare(*state))
    except Exception as error:
        print(f"ibek dev: no comparison with {source()}: {error}")


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

    _instance_report()


def _release(modules: list[str]) -> None:
    """Stop building modules from their clones. The clones are left alone."""
    nothing = []
    bad = [name for name in modules if not clones.valid_name(name)]
    if bad:
        raise _fail(f"{', '.join(bad)}: not the name of a support module")
    try:
        declared = clones.declared()
        for name in dict.fromkeys(modules):
            folder = support_folder(name) or GLOBALS.SUPPORT / name
            # the declaration goes first: a link with none is reported, and
            # nothing links the module again
            clones.declare(name, None)
            if clones.unlink(folder):
                print(f"ibek dev: removed the link {folder}: its clone is left alone")
            elif name in declared:
                print(f"ibek dev: {name} is no longer declared for development")
            else:
                nothing.append(name)
    except StampError as error:
        raise _fail(error) from error
    state = _state()
    if state is not None:
        _show(drift.compare(*state))
    if nothing:
        raise _fail(
            f"{', '.join(nothing)}: not declared for development, and no link to remove"
        )


@dev_cli.command()
def support(
    modules: list[str] = typer.Argument(
        ...,
        help="The support modules to work on, as the Dockerfile names them",
    ),
    release: bool = typer.Option(
        False,
        "--release",
        help="Stop building the modules from their clones: remove the links "
        "and the declarations, and leave the clones alone",
    ),
):
    """
    Build support modules from clones on the host, to work on their source.

    Clones each module's repository to /workspaces/<module> at the version of
    its install.yml, or uses a clone of that repository that is already
    there, with whatever it has checked out. Removes the module that the
    image built, links /epics/support/<module> to the clone, then builds it,
    the modules after it in the Dockerfile and the IOC. Run it again to build
    again after a change.

    The build edits some tracked files of a clone, such as configure/RELEASE,
    and names them: do not commit those edits.

    The modules are declared in .ibek-dev.yaml in the project. In a container
    that is created again, `ibek dev sync` reports them and
    `ibek dev sync --build` links and builds them.

    With --release, nothing is built: `ibek dev sync --build` then clones the
    modules at the version of install.yml and builds them.
    """
    _warn_stale_container()
    if release:
        _release(modules)
        return
    state = _state(strict=True)
    if state is None:
        raise typer.Exit(1)
    made, live = state
    names = live.names()
    try:
        # every module is checked, then every clone checked or made, before
        # anything in the container changes
        infos: dict[str, clones.Install] = {}
        for name in dict.fromkeys(modules):
            module = live.module(name)
            if module is None or module.build is None or not module.runs("clone"):
                raise StampError(
                    f"{name} is not a support module that the Dockerfile "
                    f"clones and builds: those are {', '.join(names)}"
                )
            infos[name] = clones.install(name, module.options)
            folder = support_folder(name)
            if folder is None:
                raise StampError(f"cannot read the install.yml of {name}")
            clone = clones.WORKSPACES / name
            if folder.is_symlink() and not clones.points_at(folder, clone):
                raise StampError(
                    f"{folder} is a link to {clones.target(folder)}, not to "
                    f"{clone}: `ibek dev support --release {name}` removes it"
                )
        # a module that follows must not lose its folder to a clone that
        # nobody has seen reported
        found = drift.compare(made, live)
        first = min(names.index(name) for name in infos)
        force = [n for n in found.force if names.index(n) >= first]
        if force:
            raise StampError(
                f"{', '.join(force)} must be cloned again, which removes "
                f"{', '.join(str(found.force[n]) for n in force)}: run "
                "`ibek dev sync --build` for that first"
            )
        plan: dict[str, Path] = {}
        for name, info in infos.items():
            clone = clones.WORKSPACES / name
            if clone.exists() or clone.is_symlink():
                clones.check(name, info, clone)
            else:
                clones.make(name, info, clone)
            if info.patch is not None:
                print(
                    f"ibek dev: {name}.install.yml applies {info.patch} to the "
                    f"clone that it makes. It is not applied to {clone}: "
                    "apply it there with `git apply` if the build needs it."
                )
            plan[name] = clone
        for name, clone in plan.items():
            clones.declare(name, clone)

        # build from the first of the modules, whatever else is out of date
        found = drift.compare(made, live)
        rebuild = [m.name for m in live.modules[first:] if m.build is not None]
        found.rebuild = rebuild
        found.force = {n: f for n, f in found.force.items() if n in rebuild}
        found.links = {n: f for n, f in found.links.items() if n in rebuild}
        found.unlinked = {n: f for n, f in found.unlinked.items() if n in rebuild}
        drift.build(made, live, found)
    except StampError as error:
        raise _fail(error) from error
    _show(drift.compare(made, live))
    # what the build printed has pushed the warning out of sight
    _warn_stale_container()
