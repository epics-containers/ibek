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

from pydantic import Field

from ibek.entity_model import EntityModel
from ibek.ioc import Entity
from ibek.parameters import Param

REPEAT_TYPE = "ibek.repeat"


# TODO this class is an idea to get the schema to work for
# the repeat's entity model.
class EntityModelParam(EntityModel, Param):
    pass


class RepeatEntity(Entity):
    """
    A definition of RepeatEntity for the type checker

    This is not really used - instead the dynamic class is created
    by the make_entity_model function is used.
    """

    type: Literal["ibek.repeat"] = "ibek.repeat"
    values: list | str = Field(
        description="The list of values to iterate over",
    )
    variable: str = Field(
        description="The variable name to use in the entity model",
        default="index",
    )
    entity: dict = Field(
        description="The entity model to repeat",
    )
