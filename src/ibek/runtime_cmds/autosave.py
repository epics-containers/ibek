"""
A class for discovering all autosave req files relating to a given DB
substitution file and generating an equivalent substitution file for
the autosave request files.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from subprocess import run

from ibek.globals import GLOBALS


def link_req_files() -> None:
    """
    Create symbolic links to autosave req files in /epics/autosave folder

    Do this is a fashion that allows overrides:
    1. expect that the folder is already populated with req files from ibek-support
    2. symlink the req files from every built support module's db folder
    2a.  but don't overwrite existing req files
    3. symlink the req files from the instance config folder
    3a.  do overwrite existing req files
    """
    Path.mkdir(GLOBALS.AUTOSAVE, exist_ok=True)
    for req in GLOBALS.SUPPORT.glob("**/*.req"):
        link = GLOBALS.AUTOSAVE / req.name
        if not link.exists():
            link.symlink_to(req)
    for req in (GLOBALS.IOC_FOLDER / GLOBALS.CONFIG_DIR_NAME).glob("*.req"):
        link = GLOBALS.AUTOSAVE / req.name
        if link.exists():
            link.unlink()
        link.symlink_to(req)


class AutosaveGenerator:
    """A class for generating autosave request files for an IOC instance"""

    @dataclass
    class SubstEntry:
        """A dataclass for storing a substitution entry"""

        template_file: Path
        pattern: str

    # https://regex101.com/r/V5cGqt/1
    entry_pat = re.compile(r'file *"?([^" ]*)"[\s\S]*?((?:{[\s\S]*?)*?}[\s\S]})')
    entry_fmt = 'file "{file}" {pattern}\n\n'

    def __init__(self, db_substitution_file: Path):
        """
        Constructor: Build a list of all of the autosave req template files
        related to each of the DB template files in db_substitution_file
        """
        self.db_substitution_file = db_substitution_file
        self.subst_entries = self.parse_subst()
        self.settings_req: dict[str, list[self.SubstEntry]] = {}  # type: ignore
        for suffix in ["settings", "positions"]:
            self.settings_req[suffix] = self.find_req(suffix)

    def generate_req_files(self) -> None:
        """
        Generate a two substitution files for settings and positions req
        template files. Execute MSI to expand these into req files.

        Use these to generate fully expanded req files for the IOC instance.
        These req files are ready to be passed to autosave in the startup script/
        """
        for suffix, entries in self.settings_req.items():
            if not entries:
                continue  # don't generate empty files

            subst_name = GLOBALS.RUNTIME_OUTPUT / f"autosave_{suffix}.subst"
            req_name = GLOBALS.RUNTIME_OUTPUT / f"autosave_{suffix}.req"

            with open(GLOBALS.RUNTIME_OUTPUT / subst_name, "w") as f:
                for entry in entries:
                    short_name = entry.template_file.name
                    f.write(
                        self.entry_fmt.format(file=short_name, pattern=entry.pattern)
                    )
            run(
                f"msi -S {subst_name} > {req_name} -I{GLOBALS.AUTOSAVE}",
                shell=True,
            )

    def parse_subst(self) -> list[SubstEntry]:
        """
        parse an EPICS DB substitution file and return a list of SubstEntry objects
        """
        result = []

        with open(self.db_substitution_file) as f:
            text = f.read()

        match = self.entry_pat.findall(text, re.MULTILINE)
        if match:
            for file, pat in match:
                result.append(self.SubstEntry(template_file=Path(file), pattern=pat))

        return result

    def find_req(self, suffix: str) -> list[SubstEntry]:
        """
        Find autosave req files for each DB template file in
        self.db_substitution_file

        These are files that have the same basename as the DB template file
        with suffix specified in the argument suffix.

        Returns a list of SubstEntry objects with their file modified to match
        the autosave req file name.
        """
        result = []

        for entry in self.subst_entries:
            stem = entry.template_file.stem
            req_file = GLOBALS.AUTOSAVE / f"{stem}_{suffix}.req"
            if req_file.exists():
                result.append(
                    self.SubstEntry(
                        template_file=req_file,
                        pattern=entry.pattern,
                    )
                )

        return result
