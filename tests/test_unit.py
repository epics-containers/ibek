"""
Some unit tests for ibek.
"""

from ibek.ioc import (
    clear_entity_model_ids,
    id_to_entity,
    make_entity_models,
    make_ioc_model,
)
from ibek.support import Definition, IdArg, ObjectArg, Support


def test_object_references():
    """
    Verify the object references are correctly resolved
    """
    clear_entity_model_ids()

    support = Support(
        module="mymodule",
        defs=[
            Definition(
                name="port",
                description="a port",
                args=[IdArg(name="name", description="an id")],
            ),
            Definition(
                name="device",
                description="a device",
                args=[ObjectArg(name="port", description="the port")],
            ),
        ],
    )

    entities = make_entity_models(support)
    ioc_model = make_ioc_model(entities)
    assert entities[0].__definition__ == support.defs[0]
    assert entities[1].__definition__ == support.defs[1]

    d = dict(
        ioc_name="",
        description="",
        entities=[
            dict(type="mymodule.port", name="PORT"),
            dict(type="mymodule.device", port="PORT"),
        ],
    )
    ioc = ioc_model(**d)
    port, device = ioc.entities
    # TODO try to get rid of the need for ''
    assert port.type == "mymodule.port"
    assert device.type == "mymodule.device"
    assert device.port is port
    assert id_to_entity == {"PORT": port}
