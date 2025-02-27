from ibek.entity_model import EntityModel
from ibek.ibek_builtin.repeat import RepeatEntity


def get_all_builtin_entity_types() -> list[EntityModel]:
    result = [
        RepeatEntity,
    ]
    return result
