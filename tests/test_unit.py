"""
Some unit tests for ibek.
"""

import dataclasses

import jinja2
import pytest
from ruamel.yaml.main import YAML

from ibek.args import IdArg, ObjectArg
from ibek.commands import semver_compare
from ibek.ioc import id_to_entity
from ibek.ioc_factory import IocFactory
from ibek.support import EntityDefinition, Support
from ibek.utils import UTILS


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
            dict(entity_type="mymodule.port", name="PORT"),
            dict(entity_type="mymodule.device", port="PORT"),
        ],
    )
    ioc = ioc_model(**d)
    port, device = ioc.entities
    # TODO try to get rid of the need for ''
    assert port.entity_type == "mymodule.port"
    assert device.entity_type == "mymodule.device"
    assert device.port is port
    assert id_to_entity == {"PORT": port}


def test_compare():
    """
    Verify the SemVer comparrisons work
    """
    assert semver_compare("1.1.1", "==1.1.1")
    assert semver_compare("1.1.1", ">=1.1.0")
    assert not semver_compare("1.1.1", ">=1.1.2")


@dataclasses.dataclass
class Person:
    name: str
    age: int


def test_strict():
    """
    validate that bad references in Jinja are caught
    """
    p = Person("giles", 59)

    my_template = "{{ person.name ~ ' of age ' ~ person.age }}"
    text = UTILS.render({"person": p}, my_template)
    assert text == "giles of age 59"

    my_template = "{{ person.name ~ ' of age ' ~ height }}"
    with pytest.raises(jinja2.exceptions.UndefinedError):
        text = UTILS.render({"person": p}, my_template)

    my_template = "{{ person.name ~ ' of age ' ~ person.height }}"
    with pytest.raises(jinja2.exceptions.UndefinedError):
        text = UTILS.render({"person": p}, my_template)


def test_dlsPLC(samples, tmp_path):
    # This test verifies that the compression of the dls_plc support file using
    # yaml anchors and aliases has resulted in the original yaml when fully expanded
    name = "dlsPLC.ibek.support.yaml"
    plc_support = samples / "support" / name
    plc_support_expanded = tmp_path / name
    plc_support_original = samples / "outputs" / name

    support_dict = YAML(typ="safe").load(plc_support)
    for definition in support_dict["defs"]:
        if "shared" in definition:
            del definition["shared"]
    YAML().dump(support_dict, plc_support_expanded)

    original_text = plc_support_original.read_text()
    expanded_text = plc_support_expanded.read_text()

    assert original_text == expanded_text
