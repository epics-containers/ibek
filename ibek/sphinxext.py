import dataclasses
from typing import Any, Dict, Optional

from apischema.json_schema.schema import Schema
from apischema.metadata.keys import SCHEMA_METADATA
from typing_extensions import Annotated, get_args, get_origin


def get_types(what: str, obj) -> Optional[Dict[str, Any]]:
    types = {}
    if what == "class" and dataclasses.is_dataclass(obj):
        # If we are a dataclass, use this
        types = {field.name: field.type for field in dataclasses.fields(obj)}
    elif what == "method":
        # Don't include the return value
        types = {
            name: annotation
            for name, annotation in obj.__annotations__.items()
            if name != "return"
        }
    return types


def get_description(args: Any) -> str:
    description = ""
    additional = []
    for arg in args:
        arg = arg.get(SCHEMA_METADATA, arg)
        if type(arg) == Schema:
            field_schema = arg.as_dict()
            for key, value in field_schema.items():
                if key == "description":
                    description = value
                else:
                    additional.append(f"{str(key)}: {str(value)}")
    if additional:
        description = description + " - " + ", ".join(additional)
    return description


def process_docstring(app, what, name, obj, options, lines):
    # Must also work for the alternative constructors such as bounded!!
    types = get_types(what, obj)
    if types:
        try:
            index = lines.index("") + 1
        except ValueError:
            lines.append("")
            index = len(lines)
        # Add types from each field
        for name, typ in types.items():
            if get_origin(typ) == Annotated:
                typ, *args = get_args(typ)
                description = get_description(args)
            else:
                description = ""
            type_name = getattr(typ, "__name__", str(typ)).replace(" ", "")
            lines.insert(
                index, f":param {type_name} {name}: {description}",
            )
            index += 1
        lines.insert(index, "")


def process_signature(app, what, name, obj, options, signature, return_annotation):
    # Recreate signature from the model
    if what == "class" and dataclasses.is_dataclass(obj):
        args = []
        for field in dataclasses.fields(obj):
            arg = field.name
            if field.default is not dataclasses.MISSING:
                arg += f"={field.default!r}"
            args.append(arg)
        signature = f'({", ".join(args)})'
        return signature, return_annotation


def setup(app):
    app.connect("autodoc-process-signature", process_signature)
    app.connect("autodoc-process-docstring", process_docstring)

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
