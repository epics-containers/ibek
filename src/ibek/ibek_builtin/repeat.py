"""
A built in entity model instance for generating N instances of another entity.

e.g.
```yaml
  - type: ibek.repeat
    variable: index
    values: {{ range(5) | list }}
    entity:
      type: ADCore.NDPvaPlugin
      NDARRAY_PORT: DET.CAM
      P: BL47P-EA-DET-01
      PORT: DET.PVA{{ index }}
      R: ":TX{{ index }}:"
      PVNAME: BL47P-EA-DET-01:TX{{ index }}:PVA
```
"""

from typing import Literal

from ibek.entity_model import EntityModel
from ibek.ioc import Entity
from ibek.parameters import DictParam, ListParam, Param, StrParam


# TODO this class is an idea to get the schema to work for
# the repeat's entity model.
class EntityModelParam(EntityModel, Param):
    pass


class RepeatEntity(Entity):
    """
    A baseclass for all generated Entity classes.
    """

    type: Literal["ibek.repeat"] = "ibek.repeat"
    entity: dict
    values: list
    variable: str


def make_entity_model() -> EntityModel:
    variable = StrParam(
        description="The variable name to use for the index in the values list",
        default="index",
    )
    values = ListParam(
        description="A list of values to use for the variable in the entity",
    )
    entity = DictParam(
        description="The entity to repeat",
    )

    model = EntityModel(
        name="repeat",
        description="A repeating entity",
        parameters={
            "variable": variable,
            "values": values,
            "entity": entity,
        },
    )
    return model
