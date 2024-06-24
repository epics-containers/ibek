"""
Some unit tests for ibek.
"""

import dataclasses
import shutil
from pathlib import Path

import jinja2
import pytest

from ibek.commands import semver_compare
from ibek.ioc import id_to_entity
from ibek.ioc_cmds.assets import extract_assets
from ibek.ioc_factory import IocFactory
from ibek.parameters import IdParam, ObjectParam
from ibek.support import EntityModel, Support
from ibek.support_cmds.commands import add_runtime_files
from ibek.utils import UTILS


def test_object_references(entity_factory):
    """
    Verify the object references are correctly resolved
    """
    support = Support(
        module="mymodule",
        entity_models=[
            EntityModel(
                name="port",
                description="a port",
                parameters={"name": IdParam(description="an id")},
            ),
            EntityModel(
                name="device",
                description="a device",
                parameters={"port": ObjectParam(description="the port")},
            ),
        ],
    )

    entities = entity_factory._make_entity_models(support)
    ioc_model = IocFactory().make_ioc_model(entities)
    assert entities[0]._model == support.entity_models[0]
    assert entities[1]._model == support.entity_models[1]

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


def test_extract_assets(tmp_epics_root: Path, samples: Path):
    """
    Test the extract_assets function
    """
    runtime_files = [
        str(tmp_epics_root / "runtime_file"),
        str(tmp_epics_root / "runtime_folder"),
    ]
    add_runtime_files(runtime_files)

    dest = Path("/tmp/ibek_test_assests")
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir()

    extract_assets(dest, tmp_epics_root, [], True)
    new_epics_root = list(dest.glob("tmp/*/*/*/epics"))[0]

    assert Path.exists(new_epics_root / "runtime_file")
    assert Path.exists(new_epics_root / "runtime_folder/text1.txt")
    assert Path.exists(new_epics_root / "runtime_folder/text2.txt")
