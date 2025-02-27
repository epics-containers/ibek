from ibek.entity_model import EntityModel
from ibek.ibek_builtin.repeat import RepeatEntity


# Note that an EntityModel instance == Entity class but the type checker
# does not know this. So a few type: ignore comments are needed.
#
# Typically all Entity classes are dynamically generated and treated as
# EntityModel instances. But the builtin entities are defined as classes
# in the ibek_builtin package and offend the type checker.
#
def get_all_builtin_entity_types() -> list[EntityModel]:
    result = [
        RepeatEntity,
    ]
    return result  # type: ignore
