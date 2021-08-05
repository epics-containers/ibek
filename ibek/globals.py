"""
A few global definitions
"""
from typing import Any, Dict, TypeVar

from apischema import schema

# A generic Type for use in type hints
T = TypeVar("T")


# a description Annotation to add to our Entity derived Types
def desc(description: str):
    return schema(description=description)


# a global namespace for holding all generated classes
namespace: Dict[str, Any] = {}
