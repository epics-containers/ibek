import os
import re
from pathlib import Path
from typing import Optional

import typer
from jinja2 import Template
from typing_extensions import Annotated

from ibek.support import Support

# note requirement for environment variable EPICS_BASE
EPICS_BASE = Path(str(os.getenv("EPICS_BASE")))
EPICS_ROOT = Path(str(os.getenv("EPICS_ROOT")))

# all support modules will reside under this directory
SUPPORT = Path(str(os.getenv("SUPPORT")))
# the global RELEASE file which lists all support modules
RELEASE = Path(f"{SUPPORT}/configure/RELEASE")
# a bash script to export the macros defined in RELEASE as environment vars
RELEASE_SH = Path(f"{SUPPORT}/configure/RELEASE.shell")
# global MODULES file used to determine order of build
MODULES = Path(f"{SUPPORT}/configure/MODULES")
# Folder containing Makefile.jinja
MAKE_FOLDER = Path(str(os.getenv("IOC"))) / "iocApp/src"
# Folder containing ibek support scripts
SCRIPTS_FOLDER = Path("/workspaces/ibek-support")

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
        text += "# PATCHED BY IBEK-SUPPORT\n-include $(TOP)/configure/RELEASE.local\n"
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


@support_cli.command()
def makefile():
    """
    get the dbd and lib files from all support modules and generate
    iocApp/src/Makefile from iocApp/src/Makefile.jinja
    """

    # use modules file to get a list of all support module folders
    # in the order of build (and hence dependency)
    modules = MODULES.read_text().split()[2:]
    # remove the IOC folder from the list
    if "IOC" in modules:
        modules.remove("IOC")

    # get all the dbd and lib files from each support module
    dbds = []
    libs = []
    for module in modules:
        folder = SCRIPTS_FOLDER / module
        dbd_file = folder / "dbd"
        if dbd_file.exists():
            dbds.extend(dbd_file.read_text().split())
        lib_file = folder / "lib"
        if lib_file.exists():
            libs.extend(lib_file.read_text().split())

    # generate the Makefile from the template
    template = Template((MAKE_FOLDER / "Makefile.jinja").read_text())
    # libraries are listed in reverse order of dependency
    libs.reverse()
    text = template.render(dbds=dbds, libs=libs)

    with (MAKE_FOLDER / "Makefile").open("w") as stream:
        stream.write(text)


# @support_cli.command
# def git_clone(
#     repo_name: str = typer.Argument(..., help="repo to clone"),
#     version: str  = typer.Argument(..., help="tag to clone"),
#     org: Optional[str] = typer.Option(
#         "https://github.com/epics-modules/", help="repo organization URL"),
#     git_args:
# ):
#     url = org + repo_name
