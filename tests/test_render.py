"""
Unit tests for the rendering of scripts and database entries from generated
Entity classes
"""
from typing import Literal

from ibek.ioc import IOC, clear_entity_model_ids
from ibek.render import Render
from ibek.render_db import RenderDb


def find_entity_class(entity_classes, entity_type):
    for entity_class in entity_classes:
        literal = Literal[entity_type]  # type: ignore
        if entity_class.model_fields["type"].annotation == literal:
            return entity_class
    else:
        raise ValueError(f"{entity_type} not found in entity_classes")


def test_pre_init_script(objects_classes):
    ref_cls = find_entity_class(objects_classes, "object_module.RefObject")

    my_ref = ref_cls(name="test_ref_object")

    render = Render()
    script_txt = render.render_script(my_ref, my_ref.__definition__.pre_init)
    assert script_txt == (
        "# This line should appear once only in the pre_init section\n"
        "# TestValues testValue\n"
        "TestValues test_ref_object.127.0.0.1\n"
    )


def test_obj_ref_script(objects_classes):
    ref_obj = find_entity_class(objects_classes, "object_module.RefObject")
    consumer = find_entity_class(objects_classes, "object_module.ConsumerTwo")

    ref_obj(name="test_ref_object")
    my_consumer = consumer(name="test_consumer", PORT="test_ref_object")

    render = Render()
    script_txt = render.render_script(my_consumer, my_consumer.__definition__.pre_init)

    assert (
        script_txt == "# ExampleTestFunction asynPortIP name port value\n"
        "ExampleTestFunction 127.0.0.1 test_consumer test_ref_object "
        "test_ref_object.127.0.0.1\n"
        "# PORT defaults to the id of PORT, i.e. PORT.name\n"
    )


def test_database_render(objects_classes, templates):
    ref_cls = find_entity_class(objects_classes, "object_module.RefObject")
    consumer = find_entity_class(objects_classes, "object_module.ConsumerTwo")

    ref_cls(name="test_ref_object")
    my_consumer = consumer(name="test_consumer", PORT="test_ref_object")

    # make a dummy IOC with two entities as database render works against
    # a whole IOC rather than a single entity at a time.
    clear_entity_model_ids()

    ioc = IOC(
        ioc_name="test_ioc",
        description="for testing",
        entities=[],
    )

    ioc.entities.append(my_consumer)
    render_db = RenderDb(ioc)
    templates = render_db.render_database()

    assert templates == {
        "test.db": [
            '"name",          "ip",        "value"                    ',
            '"test_consumer", "127.0.0.1", "test_ref_object.127.0.0.1"',
        ]
    }


def test_environment_variables(objects_classes):
    ref_cls = find_entity_class(objects_classes, "object_module.RefObject")

    ref_obj = ref_cls(name="test_ref_object")

    render = Render()
    env_text = render.render_environment_variables(ref_obj)

    assert env_text == "epicsEnvSet REF_OBJECT_NAME test_ref_object\n"


def test_entity_disabled_does_not_render_elements(objects_classes):
    # covered by tests/test_cli.py::test_build_startup_multiple
    # see disabled entities in tests/samples/yaml/objects.ibek.ioc.yaml
    pass
