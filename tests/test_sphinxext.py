from dataclasses import dataclass

from apischema import schema
from typing_extensions import Annotated as A

from ibek.sphinxext import process_docstring, process_signature


def desc(description: str):
    return schema(description=description)


@dataclass
class Thing:
    b: A[int, desc("The B")]
    c: A[str, desc("The C")] = "default"


def test_signature():
    assert process_signature(None, "class", "Thing", Thing, None, None, None) == (
        "(b, c='default')",
        None,
    )


def test_docstring():
    lines = []
    process_docstring(None, "class", "Thing", Thing, None, lines)
    assert lines == ["", ":param int b: The B", ":param str c: The C", ""]
