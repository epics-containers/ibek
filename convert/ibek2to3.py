#!/usr/bin/env python
"""
Converts .ibek.support.yaml files from the v2.0 format to the v3.0 format.
Can also convert ioc.yaml files as the changes re __utils__ are the same.

The schema changes are as follows:

- `defs` are now `entity_models`
- `args` are now `parameters`
- `parameters` are a dictionary of dictionaries instead of a list of dictionaries
- `parameters` no longer have a name field as the key in the dictionary is the name
- `values` is now `post_defines` and is also a dictionary of dictionaries
- `pre_values` is now `pre_defines` and is also a dictionary of dictionaries
- `__utils__` is now `_global`
- `_global` functions have changed:
    - `get_var` -> `get`
    - `set_var` -> `set`
    - `counter` -> `incrementor`
      - behaviour has changed: the --increment and --stop flags are interpreted
        on every invocation of the incrementor function (so non linear counters
        are possible)
      - incrementors current value is accessible via _global.get(incrementorName)

Backward compatible changes:
- object refs are literally the object - so you can modify a referenced object's
  attributes (with appropriate care!!)
- `pre_defines` and `post_defines` now may have optional `type:` which defaults to `str` and may be
    - `list` (of Any), `int`, `float`, `bool`
- each `entity_model` may have a `shared:` field which is a `list` of `Any`
- there is also a global `shared:` at the root level
- `shared:` are scratch areas in which to place anchors that can be referred to by aliases - and are therefore useful for placing repeating patterns (especially of 'parameters') and then using aliases where these repeats are required.

"""

import re
from pathlib import Path

import typer
from ruamel.yaml import YAML, CommentedMap


class ConvertedAlready(Exception):
    pass


def main(files: list[Path]):
    """
    Read a list of files in and process each one
    """
    for f in files:
        print(f"Processing {f} ...")
        process_file(f)


def tidy_up(yaml):
    # add blank lines between major fields - this is an opinionated
    # formatting choice for legibility
    for field in [
        "  - name:",
        "    databases:",
        "    pre_init:",
        "    post_init:",
        "    pre_defines:",
        "    post_defines:",
        "    shared:",
        "module",
        "entity_models",
        "      - file:",
        "      - value:",
    ]:
        # insert a blank line before the field unless it already has one
        yaml = re.sub(r"^[ \t]*(\n%s)" % field, "\n\\g<1>", yaml)
        yaml = re.sub(r"__utils__", "_global", yaml)
        yaml = re.sub(r"_ctx_", "_global", yaml)
        yaml = re.sub(r"\.counter", ".incrementor", yaml)
        yaml = re.sub(r"\.get_var", ".get", yaml)
        yaml = re.sub(r"\.setvar", ".incrementor", yaml)
    return yaml


def report(message: str):
    print(f">>>>>>> {message}")


def process_file(file: Path):
    """
    process a single file by reading its yaml - transforming it and writing it back
    """
    yaml = YAML()
    with open(file, "r") as f:
        data = yaml.load(f)

    try:
        if data is None:
            report("empty file !!")
            return

        if "module" in data:
            report("module yaml")
            convert(data)
        elif "ioc_name" in data:
            report("ioc yaml")
        else:
            report("not a supported yaml file !!")
            return

    except ConvertedAlready:
        report("already converted")
    else:
        with open(file, "w") as f:
            yaml.default_flow_style = False
            # these indents match the defaults for vscode RedHat yaml extension
            yaml.indent(mapping=2, sequence=4, offset=2)
            # we like to allow really wide lines for db subst lists etc so
            # we recommend this setting for the yaml extension
            yaml.width = 8000
            yaml.preserve_quotes = True
            yaml.dump(data, f, transform=tidy_up)


def convert(data: dict):
    """
    root data conversion function, replaces each definition in the data with
    a processed version of that definition
    """

    # replace all definitions with converted versions
    if "defs" in data:
        data["entity_models"] = [
            convert_definition(definition) for definition in data["defs"]
        ]
        del data["defs"]


def convert_definition(data: dict) -> dict | None:
    """
    convert a single definition's args list to a parameters dict
    """

    # rebuild the definition from scratch to enforce order
    new_data = CommentedMap()

    # copy the leading keys that are not being changed
    copy_verbatim(data, new_data, ["name", "description"])

    try:
        if "pre_defines" in data:
            check_converted(data["pre_defines"])
            new_data["pre_defines"] = list_to_dict(data["pre_defines"])
        if "args" in data:
            new_data["parameters"] = list_to_dict(data["args"])
        else:
            raise ConvertedAlready  # probably! (or its not a support yaml file)
        if "post_defines" in data:
            check_converted(data["post_defines"])
            new_data["post_defines"] = list_to_dict(data["post_defines"])
    except ConvertedAlready:
        raise
    except Exception:
        print(f"Failed to convert {data}")
        raise

    # copy the trailing keys that are not being changed
    copy_verbatim(
        data,
        new_data,
        [
            "pre_init",
            "post_init",
            "databases",
            "env_vars",
            "pvi",
            "shared",
            "sub_entities",
        ],
    )

    return new_data


def check_converted(item: dict | list):
    if isinstance(item, dict):
        raise ConvertedAlready


def copy_verbatim(source: dict, dest: dict, keys: list[str]):
    """
    copy keys from data to a new dictionary
    """
    for key in keys:
        if key in source:
            dest[key] = source[key]


def list_to_dict(args: list[dict]) -> dict[str, dict]:
    """
    convert a list of args to a dictionary, removing the name field as that
    becomes the key in the dictionary
    """
    parameters = CommentedMap()
    try:
        for arg in args:
            name = arg["name"]
            parameters[name] = arg.copy()
            # name is the param key so we no longer need it
            del parameters[name]["name"]
        return parameters
    except Exception:
        print(f"Failed to convert {arg}")
        raise


if __name__ == "__main__":
    typer.run(main)
