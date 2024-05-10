from typing import Sequence

from pydantic import BaseModel, Field, model_validator


class SubEntity(BaseModel, extra="allow"):
    """
    A loosely defined class to declare the Entities
    in an ibek.support.yaml file in the CollectionDefinition section
    """

    type: str = Field(description="The type of this entity")

    @model_validator(mode="after")
    def store(self):
        """
        Store the SubEntity instance in the global list of SubEntities
        """

        # empty extra implies this is the  base class being validated
        if self.model_extra is not None:
            sub_entities.append(self)
            print(f"sub-entity {self.type}")
        return self


sub_entities: Sequence[SubEntity] = []
