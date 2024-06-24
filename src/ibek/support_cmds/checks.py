"""
Helper functions for the ibek support commands.
"""

import re
import shutil
from pathlib import Path

import typer

from ibek.globals import GLOBALS, TEMPLATES

# turn RELEASE macros into bash macros
SHELL_FIND = re.compile(r"\$\(([^\)]*)\)")
SHELL_REPLACE = r"${\1}"

# find macros, including ones with blank values
PARSE_MACROS_NULL = re.compile(r"^([A-Z_\-\.a-z0-9]*)\s*=(.*)$", flags=re.M)


def verify_release_includes_local(configure_folder: Path):
    """
    Make sure that a module uses RELEASE.local.

    A git-dirtying patch is required if not.
    """
    validate_support()

    release = configure_folder / "RELEASE"
    text = release.read_text()

    if "RELEASE.local" not in text:
        typer.echo(
            f"WARNING: {configure_folder}/RELEASE does not include RELEASE.local"
        )
        typer.echo(f"WARNING: {configure_folder}/RELEASE will be patched.")
        text += "# PATCHED BY IBEK\n-include $(TOP)/configure/RELEASE.local\n"
        release.write_text(text)


def do_dependencies():
    """
    Fix up the global release file to include all support modules registered
    """
    validate_support()

    # parse the global release file
    global_release_paths = {}
    text = GLOBALS.RELEASE.read_text()
    for match in PARSE_MACROS_NULL.findall(text):
        global_release_paths[match[0]] = match[1]

    # generate the MODULES file for inclusion into the root Makefile
    # it simply defines a variable to hold each of the support module
    # directories in the order they are presented in RELEASE, except that
    s = str(GLOBALS.SUPPORT)
    paths = [
        path[len(s) + 1 :]
        for path in global_release_paths.values()
        if path.startswith(s)
    ]
    if "IOC" in global_release_paths:
        paths.append(global_release_paths["IOC"])
    mod_list = f'MODULES := {" ".join(paths)}\n'
    GLOBALS.MODULES.write_text(mod_list)

    # generate RELEASE.shell file for inclusion into the ioc launch shell script.
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
    shell_text = SHELL_FIND.sub(SHELL_REPLACE, shell_text)
    GLOBALS.RELEASE_SH.write_text(shell_text)


def check_deps(deps: list[str]) -> None:
    """
    Check if specified dependencies have been supplied
    """
    for dependency in deps:
        # Check if UCASE module name exist in RELEASE
        with open(GLOBALS.RELEASE) as file:
            release_file = file.read()
            if dependency.upper() in release_file:
                pass
            else:
                raise Exception(f"{dependency.upper()} not in {GLOBALS.RELEASE}")

        # Check if folder with the module name exist in /epics/support
        support_dir = GLOBALS.SUPPORT / dependency
        if Path.exists(support_dir):
            # Check if contains at least one of db, dbd or lib
            res = [Path.exists(support_dir / _dir) for _dir in ["db", "dbd", "lib"]]
            if any(res):
                pass
            else:
                raise Exception(f"db, dbd or lib directory not found in {support_dir}")

        else:
            raise Exception(f"{dependency} directory not in {GLOBALS.SUPPORT}")

        print(f"SUCCESS: {dependency} checked")


def add_macro(macro: str, value: str, file: Path, replace: bool = True):
    """
    add or replace a macro in a RELEASE or CONFIG file
    """
    validate_support()

    if not file.exists():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()

    text = file.read_text()

    find_m = re.compile(f"^({macro}[ \t]*=[ \t]*)(.*)$", flags=re.M)
    matches = find_m.findall(text)
    if len(matches) == 0:
        text += f"{macro}={value}\n"
    elif replace:
        text = find_m.sub(r"\1" + str(value), text)

    file.write_text(text)


def validate_support():
    """
    Validate that the support folder exists and setup initial template files
    if required
    """
    template_support = TEMPLATES / "support"
    release = Path("configure") / "RELEASE"
    global_release = GLOBALS.SUPPORT / release

    if not GLOBALS.SUPPORT.exists():
        typer.echo(f"INITIALIZING {GLOBALS.SUPPORT} folder with template")
        shutil.copytree(template_support, GLOBALS.SUPPORT)
    else:
        if not global_release.exists():
            global_release.parent.mkdir(parents=True, exist_ok=True)
            typer.echo(f"INITIALIZING {GLOBALS.SUPPORT / release} folder with template")
            shutil.copy2(template_support / release, global_release)
