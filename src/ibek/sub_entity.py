from pydantic import BaseModel, Field


class SubEntity(BaseModel, extra="allow"):
    """
    A loosely defined class to declare the Entities
    in an ibek.support.yaml file in the 'sub_entities' property of an Entity
    section
    """

    type: str = Field(description="The type of this entity")

    entity_enabled: bool = Field(
        description="enable or disable this entity instance", default=True
    )
