"""
A test to isolate the cause of the error:

Fail: TypeError: Invalid JSON type <class 'ruamel.yaml.scalarfloat.ScalarFloat'>

During Support.deserialize,
when default float values in pmac.ibek.yaml do not have a trailing 'f'

RESULT: it is due to the order of declaration of subclasses of Arg. When StrArg
is before FloatArg, apischema attempts to deserialize as a string first. The
coercion from str to number requires a trailing f if there is a decimal.
"""

from dataclasses import dataclass
from io import StringIO
from typing import Any, Literal, Mapping, Sequence, Type, TypeVar

from apischema import deserialize
from apischema.conversions.conversions import Conversion
from apischema.conversions.converters import deserializer
from apischema.conversions.utils import identity
from ruamel.yaml import YAML

""" A generic Type for use in type hints """
T = TypeVar("T")


@dataclass
class Arg:
    type: str
    default: Any

    def __init_subclass__(cls):
        deserializer(Conversion(identity, source=cls, target=Arg))


# Invert the order of the following two dataclasses to demo the Error
@dataclass
class FloatArg(Arg):
    type: Literal["float"] = "float"
    default: float = 0.0


@dataclass
class StrArg(Arg):
    type: Literal["str"] = "str"
    default: str = ""


yaml = """
args:
  - type: float
    default: 0.1
"""


@dataclass
class SomeArgs:
    args: Sequence[Arg]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)


def test_deserialize_floatarg() -> None:
    yaml_stream = StringIO(yaml)
    yaml_dict = YAML().load(yaml_stream)

    yaml_dataclass = SomeArgs.deserialize(yaml_dict)

    assert yaml_dataclass.args[0].default == 0.1
