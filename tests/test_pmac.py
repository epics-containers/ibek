import json

import apischema
from apischema.json_schema import serialization_schema

from ibek.pmac import PmacIOC


def test_make_schema() -> None:
    my_schema = serialization_schema(PmacIOC)
    with open("/tmp/pmac.schema.json", "w") as f:
        json.dump(my_schema, f)

