import ibek.ibek_builtin.repeat as repeat
from ibek.entity_model import EntityModel


def get_all_builtin_entity_types() -> list[EntityModel]:
    result = [
        repeat.make_entity_model(),
    ]
    return result
