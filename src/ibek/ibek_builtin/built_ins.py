import ibek.ibek_builtin.repeat as repeat
from ibek.ioc import Entity


def get_all_builtin_entity_types() -> list[type[Entity]]:
    result = [
        repeat.make_entity_model(),
    ]
    return result
