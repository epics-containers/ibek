import re
import subprocess
from enum import Enum
from pathlib import Path
from shutil import rmtree
from typing import List, Optional

import typer

from ibek.ioc_cmds.assets import get_ioc_source

try:
    from git import Repo
except ImportError:
    pass  # Git Python is not needed for runtime (container build time only)

from typing_extensions import Annotated

from ibek.globals import (
    IBEK_DEFS,
    IBEK_GLOBALS,
    IBEK_SUPPORT,
    IOC_DBDS,
    IOC_LIBS,
    PVI_DEFS,
    PVI_YAML_PATTERN,
    RELEASE,
    RUNTIME_DEBS,
    SUPPORT,
    SUPPORT_YAML_PATTERN,
    NaturalOrderGroup,
)
from ibek.support import Support
from ibek.support_cmds.checks import (
    add_macro,
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


@support_cli.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def apt_install(
    ctx: typer.Context,
    debs: List[str] = typer.Argument(None, help="list of debian packages to install"),
    only: AptWhen = typer.Option(
        AptWhen.both, help="which container build stage to install in"
    ),
    runtime: bool = typer.Option(False, help="install list of runtime packages"),
):
    """
    Install debian packages into the container. If they have an http:// or https://
    prefix then they will be downloaded and installed from file.
    """
    temp = Path("/tmp")

    if (only is AptWhen.run) or (only is AptWhen.both):
        add_list_to_file(RUNTIME_DEBS, debs)
    if only is AptWhen.run:
        return

    if runtime and RUNTIME_DEBS.exists():
        debs += RUNTIME_DEBS.read_text().split()

    for i, pkg in enumerate(debs):
        if pkg.startswith("http://") or pkg.startswith("https://"):
            pkg_file = temp / pkg.split("/")[-1]
            subprocess.call(["wget", pkg, "-O", str(pkg_file)])
            debs[i] = str(pkg_file)

    command = (
        "apt-get update && apt-get upgrade -y && "
        "apt-get install -y --no-install-recommends "
        + " ".join(debs)
        + " ".join(ctx.args)
    )
    exit(subprocess.call(["bash", "-c", command]))


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
    """
    url = org + repo_name
    location = SUPPORT / repo_name
    if location.exists() and not force:
        print(f"skipping {location}, already cloned")
        return
    else:
        rmtree(location, ignore_errors=True)

    Repo.clone_from(
        url, SUPPORT / repo_name, branch=version, depth=1, multi_options=ctx.args
    )


@support_cli.command()
def register(
    name: str = typer.Argument(..., help="the name of the support module"),
    path: Annotated[Optional[Path], typer.Option(help="path to support module")] = None,
    macro: Optional[str] = typer.Option(None, help="Macro name for the module"),
):
    """
    prepare the configure RELEASE files to build a support module
    inside an epics-containers build
    """
    macro = name.upper() if macro is None else macro
    path = SUPPORT / name if (path is None) else path

    # add or replace the macro for this module in the global RELEASE file
    add_macro(macro, str(path), RELEASE)

    # bring the global release file into this module with a symlink
    local = path / "configure" / "RELEASE.local"
    local.unlink(missing_ok=True)
    local.symlink_to(RELEASE)

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
    add_list_to_file(IOC_LIBS, libs)


@support_cli.command()
def add_dbds(
    dbds: List[str] = typer.Argument(None, help="list of dbd files to add"),
) -> None:
    """
    declare the dbd files for this support module for inclusion in IOC Makefile
    """
    add_list_to_file(IOC_DBDS, dbds)


@support_cli.command()
def add_release_macro(
    macro: str = typer.Argument(..., help="macro name to update"),
    value: str = typer.Argument("", help="value to set for the macro"),
    replace: bool = typer.Option(True, help="overwrite previous value"),
):
    """
    add or replace a macro the global RELEASE file
    """
    add_macro(macro, value, RELEASE, replace)


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


@support_cli.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def compile(
    ctx: typer.Context,
    module: str = typer.Argument(..., help="support module name"),
):
    """
    compile a support module after preparation with `ibek support register` etc.
    """
    path = SUPPORT / module

    command = f"make -C {path} -j $(nproc) " + " ".join(ctx.args)
    exit(subprocess.call(["bash", "-c", command]))


@support_cli.command()
def generate_links(
    support_module: Annotated[
        Path,
        typer.Argument(
            help="Support module to generate links for (directory in ibek-support)"
        ),
    ],
    ibek_support: Annotated[
        Optional[Path],
        typer.Option(
            help="Filepath to ibek-support root"
            "defaults to <generic IOC source folder>/ibek-support"
        ),
    ] = None,
):
    """Generate symlinks to the ibek and pvi YAML files for a compiled IOC.

    Args:
        support_module: Support module to generate links for
        ibek_support: Root of ibek support to find support module directory in

    """
    support_defs = (ibek_support or get_ioc_source() / IBEK_SUPPORT) / support_module
    support_globals = (ibek_support or get_ioc_source() / IBEK_SUPPORT) / IBEK_GLOBALS

    symlink_files(support_defs, SUPPORT_YAML_PATTERN, IBEK_DEFS)
    symlink_files(support_globals, SUPPORT_YAML_PATTERN, IBEK_DEFS)
    symlink_files(support_defs, PVI_YAML_PATTERN, PVI_DEFS)


@support_cli.command()
def generate_schema(
    output: Annotated[
        Optional[Path], typer.Option(help="The filename to write the schema to")
    ] = None,
):
    """Produce JSON global schema for all <support_module>.ibek.support.yaml files"""
    if output is None:
        typer.echo(Support.get_schema())
    else:
        output.write_text(Support.get_schema())
