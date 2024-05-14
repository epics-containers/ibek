"""
Some unit tests for ibek.
"""

from ibek.args import IdArg, ObjectArg
from ibek.commands import semver_compare
from ibek.ioc import id_to_entity
from ibek.ioc_factory import IocFactory
from ibek.support import EntityDefinition, Support


def test_object_references(entity_factory):
    """
    Verify the object references are correctly resolved
    """
    support = Support(
        module="mymodule",
        defs=[
            EntityDefinition(
                name="port",
                description="a port",
                args=[IdArg(name="name", description="an id")],
            ),
            EntityDefinition(
                name="device",
                description="a device",
                args=[ObjectArg(name="port", description="the port")],
            ),
        ],
    )

    entities = entity_factory._make_entity_models(support)
    ioc_model = IocFactory().make_ioc_model(entities)
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


def test_compare():
    """
    Verify the SemVer comparrisons work
    """
    assert semver_compare("1.1.1", "==1.1.1")
    assert semver_compare("1.1.1", ">=1.1.0")
    assert not semver_compare("1.1.1", ">=1.1.2")
