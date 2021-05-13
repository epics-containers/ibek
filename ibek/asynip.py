from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Type, TypeVar, Union

from apischema import Undefined, UndefinedType, deserialize, deserializer, schema
from apischema.conversions import Conversion, identity
from jinja2 import Template
from typing_extensions import Annotated as A
from typing_extensions import Literal

import ibek.support as support


@dataclass
class AsynIP:
    """ class for schema """

    pass
