from ibek.ioc import IOC, clear_entity_classes, id_to_entity, make_entity_classes
from ibek.support import Definition, IdArg, ObjectArg, Support


def test_conversion_classes():
    clear_entity_classes()
    support = Support(
        "mymodule",
        [
            Definition("port", [IdArg("name", "the name", "id")]),
            Definition("device", [ObjectArg("port", "the port", "object")]),
        ],
    )
    namespace = make_entity_classes(support)
    assert {"device", "port"}.issubset(dir(namespace))
    assert namespace.port.__definition__ == support.defs[0]
    assert namespace.device.__definition__ == support.defs[1]
    d = dict(
        ioc_name="",
        description="",
        entities=[
            dict(type="mymodule.port", name="PORT"),
            dict(type="mymodule.device", port="PORT"),
        ],
        generic_ioc_image="",
    )
    ioc = IOC.deserialize(d)
    port, device = ioc.entities
    assert port.type == "mymodule.port"
    assert id_to_entity == {"PORT": port}
    assert device.type == "mymodule.device"
    assert device.port is port
