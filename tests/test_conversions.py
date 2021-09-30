from ibek.ioc import IOC, clear_entity_classes, make_entity_classes
from ibek.support import Definition, ObjectArg, StrArg, Support


def test_conversion_classes():
    clear_entity_classes()
    support = Support(
        "mymodule",
        [
            Definition("port", [StrArg("name", "the name", is_id=True)]),
            Definition("device", [ObjectArg("port", "the port", "mymodule.port")]),
        ],
    )
    namespace = make_entity_classes(support)
    assert {"device", "port"}.issubset(dir(namespace))
    assert namespace.port.__definition__ == support.definitions[0]
    assert namespace.device.__definition__ == support.definitions[1]
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
    assert namespace.port.__instances__ == {"PORT": port}
    assert device.type == "mymodule.device"
    assert device.port is port
    assert namespace.device.__instances__ == {"0": device}
