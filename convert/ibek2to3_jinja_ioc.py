#!/usr/bin/env python
"""
converts the  __utils__ functions for ioc.yaml

Does not require that the file is valid yaml and therefore works for jinja
templated IOCs
"""

import re
from pathlib import Path


def main(files: list[Path]):
    """
    Read a list of files in and process each one
    """
    for f in files:
        print(f"Processing {f} ...")
        process_file(f)


def report(message: str):
    print(f">>>>>>> {message}")


def process_file(file: Path):
    """
    process a single file by reading its yaml - transforming it and writing it back
    """
    this_file = Path(file)
    data = this_file.read()

    if data is None:
        report("empty file !!")
    elif "ioc_name" in data:
        report("ioc yaml")
        data = tidy_up(data)
        this_file.write(data)
    else:
        report("not a supported yaml file !!")


def tidy_up(yaml):
    yaml = re.sub(r"__utils__", "_global", yaml)
    yaml = re.sub(r"_ctx_", "_global", yaml)
    yaml = re.sub(r"\.counter", ".incrementor", yaml)
    yaml = re.sub(r"\.get_var", ".get", yaml)
    yaml = re.sub(r"\.setvar", ".incrementor", yaml)
    return yaml
