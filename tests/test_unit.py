"""
Some unit tests for ibek.
"""

import dataclasses

import pytest
from pydantic import ValidationError

from ibek.entity_model import Validation
from ibek.ioc import clear_entity_model_ids, id_to_entity
from ibek.ioc_factory import IocFactory
from ibek.parameters import IdParam, ObjectParam
from ibek.support import EntityModel, Support
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

    entities = entity_factory._make_entity_types(support)
    ioc_model = IocFactory().make_ioc_model(entities)
    assert entities[0]._model == support.entity_models[0]
    assert entities[1]._model == support.entity_models[1]

    d = {
        "ioc_name": "",
        "description": "",
        "entities": [
            {"type": "mymodule.port", "name": "PORT"},
            {"type": "mymodule.device", "port": "PORT"},
        ],
    }
    ioc = ioc_model(**d)
    port, device = ioc.entities
    # TODO try to get rid of the need for ''
    assert port.type == "mymodule.port"
    assert device.type == "mymodule.device"
    assert device.port is port
    assert id_to_entity == {"PORT": port}


def make_validated_ioc_model(entity_factory, validate: list[dict]):
    """
    Make an IOC model from a support module whose 'device' entity model has
    the given validate list. The support is built from a dict so that the
    YAML 'assert' key is used.
    """
    support = Support.model_validate(
        {
            "module": "mymodule",
            "entity_models": [
                {
                    "name": "port",
                    "description": "a port",
                    "parameters": {
                        "name": {"type": "id", "description": "an id"},
                        "count": {
                            "type": "int",
                            "description": "a count",
                            "default": 1,
                        },
                    },
                },
                {
                    "name": "device",
                    "description": "a device",
                    "parameters": {
                        "port": {"type": "object", "description": "the port"},
                        "gain": {"type": "int", "description": "a gain"},
                    },
                    "post_defines": {
                        "double_gain": {
                            "description": "twice the gain",
                            "type": "int",
                            "value": "{{ gain * 2 }}",
                        }
                    },
                    "validate": validate,
                },
            ],
        }
    )
    entities = entity_factory._make_entity_types(support)
    return IocFactory().make_ioc_model(entities)


def make_ioc_dict(gain: int, count: int = 1, enabled: bool = True) -> dict:
    return {
        "ioc_name": "",
        "description": "",
        "entities": [
            {"type": "mymodule.port", "name": "PORT", "count": count},
            {
                "type": "mymodule.device",
                "port": "PORT",
                "gain": gain,
                "entity_enabled": enabled,
            },
        ],
    }


def test_validate_assert_key():
    """
    The YAML key is 'assert' and maps to the assert_ attribute
    """
    model = EntityModel.model_validate(
        {
            "name": "device",
            "description": "a device",
            "validate": [{"assert": "gain > 0", "message": "bad gain"}],
        }
    )
    assert model.validate_ == [Validation(assert_="gain > 0", message="bad gain")]

    with pytest.raises(ValidationError):
        Validation.model_validate({"assert": "True", "message": "", "extra": 1})


def test_validate_pass(entity_factory):
    ioc_model = make_validated_ioc_model(
        entity_factory,
        [
            {"assert": "gain > 0", "message": "gain must be positive"},
            {"assert": "double_gain == 2 * gain", "message": "post_define"},
        ],
    )
    ioc = ioc_model(**make_ioc_dict(gain=3))
    assert ioc.entities[1].double_gain == 6


def test_validate_fail(entity_factory):
    ioc_model = make_validated_ioc_model(
        entity_factory,
        [{"assert": "gain > 0", "message": "gain {{ gain }} must be positive"}],
    )
    with pytest.raises(ValidationError) as exc:
        ioc_model(**make_ioc_dict(gain=-1))
    assert "mymodule.device: validation failed: gain -1 must be positive" in str(
        exc.value
    )


def test_validate_object_reference(entity_factory):
    ioc_model = make_validated_ioc_model(
        entity_factory,
        [
            {
                "assert": "port.count > 1",
                "message": "port {{ port }} needs count > 1",
            }
        ],
    )
    ioc = ioc_model(**make_ioc_dict(gain=1, count=2))
    assert ioc.entities[1].port.count == 2

    # instantiate a second IOC with the same ids
    clear_entity_model_ids()
    with pytest.raises(ValidationError) as exc:
        ioc_model(**make_ioc_dict(gain=1, count=1))
    assert "mymodule.device: validation failed: port PORT needs count > 1" in str(
        exc.value
    )


def test_validate_disabled_entity(entity_factory):
    ioc_model = make_validated_ioc_model(
        entity_factory,
        [{"assert": "gain > 0", "message": "gain must be positive"}],
    )
    ioc = ioc_model(**make_ioc_dict(gain=-1, enabled=False))
    assert ioc.entities[1].entity_enabled is False


def test_validate_undefined_name(entity_factory):
    ioc_model = make_validated_ioc_model(
        entity_factory,
        [{"assert": "gian > 0", "message": "gain must be positive"}],
    )
    with pytest.raises(ValidationError) as exc:
        ioc_model(**make_ioc_dict(gain=1))
    assert "mymodule.device: could not evaluate validation 'gian > 0'" in str(exc.value)
    assert "'gian' is undefined" in str(exc.value)


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
    with pytest.raises(ValueError):
        text = UTILS.render({"person": p}, my_template)

    my_template = "{{ person.name ~ ' of age ' ~ person.height }}"
    with pytest.raises(ValueError):
        text = UTILS.render({"person": p}, my_template)


# TODO this needs a pre-created epics-root instead of adding its
# def test_extract_assets(tmp_epics_root: Path, samples: Path):
#     """
#     Test the extract_assets function
#     """
#     runtime_files = [
#         str(tmp_epics_root / "runtime_file"),
#         str(tmp_epics_root / "runtime_folder"),
#     ]
#     add_runtime_files(runtime_files)

#     dest = Path("/tmp/ibek_test_assests")
#     shutil.rmtree(dest, ignore_errors=True)
#     dest.mkdir()

#     extract_assets(dest, tmp_epics_root, [], True)
#     new_epics_root = list(dest.glob("tmp/*/*/*/epics"))[0]

#     assert Path.exists(new_epics_root / "runtime_file")
#     assert Path.exists(new_epics_root / "runtime_folder/text1.txt")
#     assert Path.exists(new_epics_root / "runtime_folder/text2.txt")
