"""
A built in entity model for generating N instances of another entity.

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

from ibek.entity_model import EntityModel


def make_entity_model() -> EntityModel:
    model = EntityModel(
        name="repeat",
        description="A repeating entity",
        parameters={},
        #     "variable": StrParam,
        #     "values": StrParam,
        #     "entity": EntityModel,
        # },
    )
    return model
