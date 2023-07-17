from __future__ import annotations

from typing import Dict, Literal, Optional, Sequence, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    create_model,
    field_validator,
    model_validator,
)

id_to_entity: Dict[str, Entity] = {}


class Entity(BaseModel):
    type: str = Field(description="The type of this entity")
    name: str = Field(..., description="The name of this entity")
    value: str = Field(..., description="The value of this entity")
    ref: Optional[str] = Field(
        default=None, description="Reference another Entity name"
    )
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")  # type: ignore
    def add_ibek_attributes(cls, entity: Entity):
        id_to_entity[entity.name] = entity

        return entity


class Entity1(Entity):
    type: Literal["e1"] = Field(description="The type of this entity")


class Entity2(Entity):
    type: Literal["e2"] = Field(description="The type of this entity")


@field_validator("ref", mode="after")
def lookup_instance(cls, id):
    try:
        return id_to_entity[id]
    except KeyError:
        raise KeyError(f"object {id} not found in {list(id_to_entity)}")


validators = {"Entity": lookup_instance}

# add validator to the Entity classes using create model
EntityOne = create_model(
    "EntityOne",
    __validators__=validators,
    __base__=Entity1,
)  # type: ignore

EntityTwo = create_model(
    "EntityTwo",
    __validators__=validators,
    __base__=Entity2,
)  # type: ignore

entity_models = (EntityOne, EntityTwo)


class EntityModel(RootModel):
    root: Union[entity_models] = Field(discriminator="type")  # type: ignore


class Entities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entities: Sequence[EntityModel] = Field(  # type: ignore
        description="List of entities classes we want to create"
    )


model1 = Entities(
    **{
        "entities": [
            {"type": "e1", "name": "one", "value": "OneValue"},
            {"type": "e2", "name": "two", "value": "TwoValue", "ref": "one"},
        ]
    }
)

# demonstrate that entity one has a reference to entity two
assert model1.entities[1].root.ref.value == "OneValue"

# this should throw an error because entity one has illegal arguments
model2 = Entities(
    **{
        "entities": [
            {"type": "e2", "name": "two", "value": "TwoValue", "ref": "one"},
            {
                "type": "e1",
                "name": "one",
                "value": "OneValue",
                "illegal": "bad argument",
            },
        ]
    }
)
