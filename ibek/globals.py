"""
A few global defintions
"""
from typing import TypeVar

from apischema import schema

#: A generic Type for use in type hints
T = TypeVar("T")


def desc(description: str):
    """ a description Annotation to add to our Entity derived Types """
    return schema(description=description)
