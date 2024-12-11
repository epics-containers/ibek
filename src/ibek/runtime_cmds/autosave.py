"""
A class for discovering all autosave req files relating to a given DB
substitution file and generating an equivalent substitution file for
the autosave request files.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from ibek.globals import GLOBALS


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
        self.db_substitution_file = db_substitution_file
        self.subst_entries = self.parse_subst()
        self.settings_req: Dict[str, List[self.SubstEntry]] = {}
        for suffix in ["_settings.req", "_positions.req"]:
            self.settings_req[suffix] = self.find_req(suffix)

    def generate_req_files(self) -> None:
        """
        Generate a two substitution files for settings and positions req
        template files.

        Use these to generate fully expanded req files for the IOC instance.
        These req files are ready to be passed to autosave in the startup script/
        """
        for suffix, entries in self.settings_req.items():
            with open(GLOBALS.RUNTIME_OUTPUT / f"autosave{suffix}", "w") as f:
                for entry in entries:
                    f.write(
                        self.entry_fmt.format(
                            file=entry.template_file, pattern=entry.pattern
                        )
                    )

    def parse_subst(self) -> List[SubstEntry]:
        """
        parse an EPICS DB substitution file and return a list of SubstEntry objects
        """
        result = []

        with open(self.db_substitution_file, "r") as f:
            text = f.read()

        match = self.entry_pat.findall(text, re.MULTILINE)
        if match:
            for file, pat in match:
                result.append(self.SubstEntry(template_file=Path(file), pattern=pat))

        return result

    def find_req(self, req_suffix: str) -> List[SubstEntry]:
        """
        Find autosave req files for each DB template file in
        self.db_substitution_file

        These are files that have the same basename as the DB template file
        with suffix specified with req_suffix.

        Returns a list of SubstEntry objects with their file modified to match
        the autosave req file name.
        """
        result = []

        for entry in self.subst_entries:
            stem = entry.template_file.stem
            search_paths = self.get_search_paths(entry.template_file)
            for path in search_paths:
                req_file = path / f"{stem}{req_suffix}"
                if req_file.exists():
                    result.append(
                        self.SubstEntry(template_file=req_file, pattern=entry.pattern)
                    )
                    break

        return result

    def get_search_paths(self, db_template: Path) -> List[Path]:
        """
        Get a list of paths to search for autosave req files
        """
        # instance req overrides are supplied in the instance config folder
        config = GLOBALS.IOC_FOLDER / GLOBALS.CONFIG_DIR_NAME
        # support module overrides from ibek-support are in AUTOSAVE_OVERRIDES
        result = [config, GLOBALS.AUTOSAVE_OVERRIDES]

        if str(db_template.parent) == ".":
            # search in all db folders if there is no path in the template name
            result += GLOBALS.SUPPORT.glob("**/db")
        else:
            # TODO this should search only in the template's parent folder
            # but that will require expanding environment variables if found
            # in the path
            result += GLOBALS.SUPPORT.glob("**/db")
            # TODO for now this is OK but it will have problems if there are
            # duplicate template names

        return result
