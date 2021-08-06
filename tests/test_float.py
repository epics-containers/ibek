"""
A test to isolate the cause of the error:

Fail: TypeError: Invalid JSON type <class 'ruamel.yaml.scalarfloat.ScalarFloat'>

During Support.deserialize,
when default float values in pmac.ibek.yaml do not have a trailing 'f'
"""

from dataclasses import dataclass
from io import StringIO
from typing import Any, Literal, Mapping, Optional, Sequence, Type, TypeVar, Union

from apischema import deserialize, schema
from apischema.conversions.conversions import Conversion
from apischema.conversions.converters import deserializer
from apischema.conversions.utils import identity
from apischema.utils import Undefined, UndefinedType
from ruamel.yaml import YAML
from typing_extensions import Annotated as A

# from ibek.argument import Arg

""" A generic Type for use in type hints """
T = TypeVar("T")


def desc(description: str):
    """ a description Annotation to add to our Entity derived Types """
    return schema(description=description)


Default = A[
    Union[Optional[T], UndefinedType],
    desc("If given, and instance doesn't supply argument, what value should be used"),
]


@dataclass
class Arg2:
    """Base class for all Argument Types"""

    name: A[str, desc("Name of the argument that the IOC instance should pass")]
    description: A[str, desc("Description of what the argument will be used for")]
    type: str
    default: Any

    # https://wyfo.github.io/apischema/examples/subclass_union/
    def __init_subclass__(cls):
        # Deserializers stack directly as a Union
        deserializer(Conversion(identity, source=cls, target=Arg2))


@dataclass
class FloatArg(Arg2):
    type: Literal["float"] = "float"
    default: Default[Union[float, str]] = Undefined


@dataclass
class IntArg(Arg2):
    """An argument with an int value"""

    type: Literal["int"] = "int"
    default: Default[Union[int, str]] = Undefined


@dataclass
class StrArg(Arg2):
    """An argument with a str value"""

    type: Literal["str"] = "str"
    default: Default[str] = Undefined
    is_id: A[
        bool, desc("If true, instances may refer to this instance by this arg")
    ] = False


@dataclass
class SomeArgs:
    args: Sequence[Arg2]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)


@dataclass
class ObjectArg(Arg2):
    """A reference to another entity defined in this IOC"""

    type: A[str, desc("Entity class, <module>.<entity_name>")]
    default: Default[str] = Undefined


yaml = """
args:
  - type: float
    name: MRES
    description: Motor Step Size (EGU)
    default: 0.1
"""


def test_deserialize_floatarg() -> None:
    yaml_stream = StringIO(yaml)
    yaml_dict = YAML().load(yaml_stream)

    yaml_dataclass = SomeArgs.deserialize(yaml_dict)

    assert yaml_dataclass.args[0].default == 0.1
