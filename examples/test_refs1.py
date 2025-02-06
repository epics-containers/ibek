from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

id_to_entity: dict[str, Entity] = {}


class Entity(BaseModel):
    name: str = Field(..., description="The name of this entity")
    value: str = Field(..., description="The value of this entity")
    ref: str | None = Field(default=None, description="Reference another Entity name")
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")  # type: ignore
    def add_ibek_attributes(cls, entity: Entity):
        id_to_entity[entity.name] = entity

        return entity

    @field_validator("ref", mode="after")
    def lookup_instance(cls, id):
        try:
            return id_to_entity[id]
        except KeyError as e:
            raise KeyError(f"object {id} not found in {list(id_to_entity)}") from e


class Entities(BaseModel):
    entities: list[Entity] = Field(..., description="The entities in this model")


model1 = Entities(
    **{  # type: ignore
        "entities": [
            {"name": "one", "value": "OneValue"},
            {"name": "two", "value": "TwoValue", "ref": "one"},
        ]
    }
)

# demonstrate that entity two has a reference to entity one
assert model1.entities[1].ref.value == "OneValue"  # type: ignore

# this should throw an error because entity one_again has illegal arguments
# BUT the error shown is:
#    KeyError: "object one_again not found in ['one', 'two']"
# which masks the underlying schema violation error that should look like:
#    Extra inputs are not permitted [type=extra_forbidden, input_value='bad argument',
model2 = Entities(
    **{  # type: ignore
        "entities": [
            {"name": "one_again", "value": "OneValue", "illegal": "bad argument"},
            {"name": "two_again", "value": "TwoValue", "ref": "one_again"},
        ]
    }
)
