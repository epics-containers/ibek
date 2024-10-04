import os
import re
import subprocess
from enum import Enum
from pathlib import Path
from shutil import rmtree
from typing import List, Optional

import typer

try:
    from git import Repo
except ImportError:
    pass  # Git Python is not needed for runtime (container build time only)

from typing_extensions import Annotated

from ibek.globals import (
    GLOBALS,
    PVI_YAML_PATTERN,
    SUPPORT_YAML_PATTERN,
    NaturalOrderGroup,
)
from ibek.support import Support
from ibek.support_cmds.checks import (
    add_macro,
    check_deps,
    do_dependencies,
    verify_release_includes_local,
)
from ibek.support_cmds.files import (
    Arch,
    add_list_to_file,
    add_text_once,
    get_config_site_file,
    symlink_files,
)


class AptWhen(str, Enum):
    dev = "dev"
    run = "run"
    both = "both"


# find macro name and macro value in a RELEASE file
# only include values with at least one / (attempt to match filepaths only)
PARSE_MACROS = re.compile(r"^([A-Z_a-z0-9]*)\s*=\s*(.*/.*)$", flags=re.M)


support_cli = typer.Typer(cls=NaturalOrderGroup)


def _install_debs(debs: List[str]) -> None:
    """
    Install a list of debian packages.

    If they have an http:// or https://
    prefix then they will be downloaded and installed from file.

    args: debs: List[str] - list of debian packages to install - can also include
                            any additional 'apt-get install' options required
    """
    temp = Path("/tmp")
    for i, pkg in enumerate(debs):
        if pkg.startswith("http://") or pkg.startswith("https://"):
            pkg_file = temp / pkg.split("/")[-1]
            subprocess.call(["busybox", "wget", pkg, "-O", str(pkg_file)])
            debs[i] = str(pkg_file)

    if len(debs) == 0:
        print("no packages to install")
        return

    print("installing packages: ", debs)

    sudo = "sudo" if os.geteuid() != 0 else ""
    command = (
        f"{sudo} apt-get update && {sudo} apt-get upgrade -y && "
        f"{sudo} apt-get install -y --no-install-recommends " + " ".join(debs)
    )
    exit(subprocess.call(["bash", "-c", command]))


@support_cli.command()
def apt_install(
    debs: List[str] = typer.Argument(
        None,
        help=(
            "list of debian packages to install. Also may include any "
            "additional 'apt-get install' options required"
        ),
    ),
):
    """
    Install packages
    """
    debs = debs or []
    _install_debs(debs)


@support_cli.command()
def add_runtime_packages(
    debs: List[str] = typer.Argument(None, help="list of debian packages to install"),
):
    """
    Add packages to RUNTIME_DEBS for later install with apt_install_runtime_packages

    The list may include any additional 'apt-get install' options required.
    """
    debs = debs or []
    add_list_to_file(GLOBALS.RUNTIME_DEBS, debs)


@support_cli.command()
def apt_install_runtime_packages(
    skip_non_native: bool = typer.Option(
        False, help="skip installation in cross-compile environment"
    ),
):
    """
    Install packages from the list collected by calls to add_runtime_packages
    """
    if not GLOBALS.NATIVE and skip_non_native:
        print("skipping runtime install in cross-compile environment")
        return

    if GLOBALS.RUNTIME_DEBS.exists():
        debs = GLOBALS.RUNTIME_DEBS.read_text().split()
        _install_debs(debs)


@support_cli.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def git_clone(
    ctx: typer.Context,
    repo_name: str = typer.Argument(..., help="repo to clone"),
    version: str = typer.Argument(..., help="tag to clone"),
    org: str = typer.Option(
        "https://github.com/epics-modules/", help="repo organization URL"
    ),
    force: bool = typer.Option(False, help="overwrite existing clone"),
):
    """
    clone a support module from a remote repository

    Add any additional arguments to the git clone command at the end of the
    argument list.
    """
    org = org if org.endswith("/") else org + "/"
    url = org + repo_name
    location = GLOBALS.SUPPORT / repo_name
    if location.exists() and not force:
        print(f"skipping {location}, already cloned")
        return
    else:
        rmtree(location, ignore_errors=True)

    Repo.clone_from(
        url,
        GLOBALS.SUPPORT / repo_name,
        branch=version,
        depth=1,
        multi_options=ctx.args,
    )


@support_cli.command()
def register(
    name: str = typer.Argument(..., help="the name of the support module"),
    path: Annotated[
        Optional[Path],
        typer.Option(
            help="path to support module",
            autocompletion=lambda: [],  # Forces path autocompletion
        ),
    ] = None,
    macro: Optional[str] = typer.Option(None, help="Macro name for the module"),
):
    """
    prepare the configure RELEASE files to build a support module
    inside an epics-containers build
    """
    macro = name.upper() if macro is None else macro
    path = GLOBALS.SUPPORT / name if (path is None) else path

    # add or replace the macro for this module in the global RELEASE file
    add_macro(macro, str(path), GLOBALS.RELEASE)

    # bring the global release file into this module with a symlink
    local = path / "configure" / "RELEASE.local"
    local.unlink(missing_ok=True)
    local.symlink_to(GLOBALS.RELEASE)

    # make sure this module uses RELEASE.local
    verify_release_includes_local(path / "configure")

    do_dependencies()


@support_cli.command()
def add_libs(
    libs: List[str] = typer.Argument(None, help="list of libraries to add"),
) -> None:
    """
    declare the libraries for this support module for inclusion in IOC Makefile
    """
    libs = libs or []
    add_list_to_file(GLOBALS.IOC_LIBS, libs)


@support_cli.command()
def add_dbds(
    dbds: List[str] = typer.Argument(None, help="list of dbd files to add"),
) -> None:
    """
    declare the dbd files for this support module for inclusion in IOC Makefile
    """
    dbds = dbds or []
    add_list_to_file(GLOBALS.IOC_DBDS, dbds)


@support_cli.command()
def add_release_macro(
    macro: str = typer.Argument(..., help="macro name to update"),
    value: str = typer.Argument("", help="value to set for the macro"),
    replace: bool = typer.Option(True, help="overwrite previous value"),
):
    """
    add or replace a macro the global RELEASE file
    """
    add_macro(macro, value, GLOBALS.RELEASE, replace)


@support_cli.command()
def add_config_macro(
    name: str = typer.Argument(..., help="the name of the support module"),
    macro: str = typer.Argument(..., help="macro name to update"),
    value: str = typer.Argument("", help="value to set for the macro"),
    replace: bool = typer.Option(True, help="overwrite previous value"),
    host: Annotated[Arch, typer.Option(case_sensitive=False)] = Arch.x86_64,
    target: Annotated[Arch, typer.Option(case_sensitive=False)] = Arch.common,
):
    """
    add or replace a macro in CONFIG_SITE.linux-x86_64.Common file
    """
    config_site = get_config_site_file(name, host, target)
    add_macro(macro, value, config_site, replace)


@support_cli.command()
def add_to_config_site(
    module: str = typer.Argument(..., help="support module name"),
    text: str = typer.Argument(..., help="text to add in an idempotent fashion"),
    host: Annotated[Arch, typer.Option(case_sensitive=False)] = Arch.x86_64,
    target: Annotated[Arch, typer.Option(case_sensitive=False)] = Arch.common,
):
    """
    add some text to a support module's CONFIG_SITE file
    """

    # nothing to do if text is blank
    if text != "":
        config_site = get_config_site_file(module, host, target)
        add_text_once(config_site, text)


@support_cli.command()
def check_dependencies(
    deps: List[str] = typer.Argument(help="list of dependencies to check"),
):
    """
    Check if specified dependencies have been supplied
    """
    check_deps(deps)


@support_cli.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def compile(
    ctx: typer.Context,
    module: str = typer.Argument(..., help="support module name"),
):
    """
    compile a support module after preparation with `ibek support register` etc.

    Add any extra compiler options to the end of the argument list
    """
    path = GLOBALS.SUPPORT / module

    command = f"make -C {path} -j $(nproc) " + " ".join(ctx.args)
    result = subprocess.call(["bash", "-c", command])
    if result == 0:
        # save size of developer container with make clean
        command = f"make -C {path} -j $(nproc) clean"
        subprocess.call(["bash", "-c", command])
    exit(result)


@support_cli.command()
def generate_links(
    folder: Annotated[
        Path,
        typer.Argument(
            help="ibek-support(-xxx) folder to generate links for",
            autocompletion=lambda: [],  # Forces path autocompletion
        ),
    ],
):
    """Generate symlinks to the ibek and pvi YAML files for a compiled IOC.

    Args:
        folder: path to an ibek-support folder containing the YAML files
                for the support module to link to. This should be a sub
                module of the ioc-xxx Generic IOC project and may be the
                public ibek-support repo or a private ibek-support-xxx repo.
    """
    symlink_files(folder, SUPPORT_YAML_PATTERN, GLOBALS.IBEK_DEFS)
    symlink_files(folder, PVI_YAML_PATTERN, GLOBALS.PVI_DEFS)


@support_cli.command()
def generate_schema(
    output: Annotated[
        Optional[Path],
        typer.Option(
            help="The filename to write the schema to",
            autocompletion=lambda: [],  # Forces path autocompletion
        ),
    ] = None,
):
    """Produce JSON global schema for all <support_module>.ibek.support.yaml files"""
    if output is None:
        typer.echo(Support.get_schema())
    else:
        output.write_text(Support.get_schema())


@support_cli.command()
def add_runtime_files(
    files: List[str] = typer.Argument(
        None, help="list of file or folders to add to the runtime image"
    ),
):
    """
    Adds to the list of folders or filesthat are copied over to the runtime
    stage of the container build.
    """
    files = files or []
    add_list_to_file(GLOBALS.RUNTIME_FILES, files)
