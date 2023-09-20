import re
import subprocess
from pathlib import Path
from shutil import rmtree
from typing import List, Optional

import typer
from git import Repo
from typing_extensions import Annotated

from ibek.files import Arch, add_text_once, get_config_site_file
from ibek.globals import EPICS_ROOT, MODULES, RELEASE, RELEASE_SH, SUPPORT
from ibek.support import Support

from ibek.globals import IOC_LIBS, IOC_DBDS

from ibek.files import add_list_to_file

# find macro name and macro value in a RELEASE file
# only include values with at least one / (attempt to match filepaths only)
PARSE_MACROS = re.compile(r"^([A-Z_a-z0-9]*)\s*=\s*(.*/.*)$", flags=re.M)
# like the above but allows any value including blank
PARSE_MACROS_NULL = re.compile(r"^([A-Z_a-z0-9]*)\s*=(.*)$", flags=re.M)
# turn RELEASE macros into bash macros
SHELLIFY_FIND = re.compile(r"\$\(([^\)]*)\)")
SHELLIFY_REPLACE = r"${\1}"


support_cli = typer.Typer()


@support_cli.command()
def generate_schema(
    output: Path = typer.Argument(..., help="The filename to write the schema to")
):
    """Produce JSON global schema for all <support_module>.ibek.support.yaml files"""
    output.write_text(Support.get_schema())


@support_cli.command()
def add_macro(
    macro: str = typer.Argument(..., help="macro name to update"),
    value: str = typer.Argument("", help="value to set for the macro"),
    file: Annotated[Path, typer.Option()] = RELEASE,
    replace: bool = typer.Option(True, help="overwrite previous value"),
):
    """
    add or replace a macro in a RELEASE file
    """
    text = file.read_text()

    find_m = re.compile(f"^({macro}[ \t]*=[ \t]*)(.*)$", flags=re.M)
    matches = find_m.findall(text)
    if len(matches) == 0:
        text += f"{macro}={value}\n"
    elif replace:
        text = find_m.sub(r"\1" + str(value), text)

    file.write_text(text)


@support_cli.command()
def register(
    name: str = typer.Argument(..., help="the name of the support module"),
    path: Annotated[Optional[Path], typer.Option()] = None,
    macro: Optional[str] = typer.Option(None, help="Macro name for the module"),
):
    """
    prepare the configure RELEASE files to build a support module
    inside an epics-containers build
    """
    macro = name.upper() if macro is None else macro
    path = EPICS_ROOT / "support" / name if (path is None) else path

    # add or replace the macro for this module in the global RELEASE file
    add_macro(macro, str(path))

    # bring the global release file into this module with a symlink
    local = path / "configure" / "RELEASE.local"
    local.unlink(missing_ok=True)
    local.symlink_to(RELEASE)

    # make sure this module uses RELEASE.local
    verify_release_includes_local(path / "configure")

    do_dependencies()


def verify_release_includes_local(configure_folder: Path):
    """
    Make sure that a module uses RELEASE.local.

    A git-dirtying patch is required if not.
    """
    release = configure_folder / "RELEASE"
    text = release.read_text()

    if "RELEASE.local" not in text:
        print(f"WARNING: {configure_folder}/RELEASE does not include RELEASE.local")
        text += "# PATCHED BY IBEK\n-include $(TOP)/configure/RELEASE.local\n"
        release.write_text(text)


def do_dependencies():
    # parse the global release file
    global_release_paths = {}
    text = RELEASE.read_text()
    for match in PARSE_MACROS_NULL.findall(text):
        global_release_paths[match[0]] = match[1]

    # generate the MODULES file for inclusion into the root Makefile
    # it simply defines a variable to hold each of the support module
    # directories in the order they are presented in RELEASE, except that
    s = str(SUPPORT)
    paths = [
        path[len(s) + 1 :]
        for path in global_release_paths.values()
        if path.startswith(s)
    ]
    if "IOC" in global_release_paths:
        paths.append(global_release_paths["IOC"])
    mod_list = f'MODULES := {" ".join(paths)}\n'
    MODULES.write_text(mod_list)

    # generate RELEASE.sh file for inclusion into the ioc launch shell script.
    # This adds all module paths to the environment and also adds their db
    # folders to the database search path env variable EPICS_DB_INCLUDE_PATH
    release_sh = []
    for module, path in global_release_paths.items():
        release_sh.append(f'export {module}="{path}"')

    db_paths = [
        f"{path}/db" for path in global_release_paths.values() if path.startswith(s)
    ]
    db_path_list = ":".join(db_paths)
    release_sh.append(f'export EPICS_DB_INCLUDE_PATH="{db_path_list}"')

    shell_text = "\n".join(release_sh) + "\n"
    shell_text = SHELLIFY_FIND.sub(SHELLIFY_REPLACE, shell_text)
    RELEASE_SH.write_text(shell_text)


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
def add_libs(
    module: str = typer.Argument(..., help="support module name"),
    libs: List[str] = typer.Argument(..., help="list of libraries to add"),
) -> None:
    """
    declare the libraries for this support module for inclusion in IOC Makefile
    """
    add_list_to_file(IOC_LIBS, libs)


@support_cli.command()
def add_dbds(
    module: str = typer.Argument(..., help="support module name"),
    dbds: List[str] = typer.Argument(..., help="list of dbd files to add"),
) -> None:
    """
    declare the dbd files for this support module for inclusion in IOC Makefile
    """
    add_list_to_file(IOC_DBDS, dbds)



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
    command_list = ["bash", "-c", command]

    result = subprocess.call(command_list)

    exit(result)


@support_cli.command()
def generate_links(
    module: str = typer.Argument(..., help="support module name"),
):
    """
    generate symlinks to the bob, pvi and support YAML for a compiled IOC
    """
    # TODO


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
