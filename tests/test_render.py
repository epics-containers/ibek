"""
Unit tests for the rendering of scripts and database entries from generated
Entity classes
"""

from typing import Literal

from ibek.render import Render
from ibek.render_db import RenderDb


def find_entity_class(entity_classes, type):
    for entity_class in entity_classes:
        literal = Literal[type]  # type: ignore
        if entity_class.model_fields["type"].annotation == literal:
            return entity_class
    else:
        raise ValueError(f"{type} not found in entity_classes")


def test_pre_init_script(asyn_classes):
    definition = find_entity_class(asyn_classes, "asyn.AsynIP")

    # NOTE: because we have switched from type to type in the
    # we need to pass it to the constructor
    # Not ideal - but does not affect deserialization of these types
    port1 = definition(name="asyn1", port="10.0.1.1", type="asyn.AsynIP")
    port2 = definition(name="asyn2", port="10.0.1.2", type="asyn.AsynIP")

    render = Render()
    script_txt = render.render_script(port1, port1._model.pre_init)
    script_txt += render.render_script(port2, port2._model.pre_init)
    assert script_txt == (
        "# Setting up Asyn Port asyn1 on 10.0.1.1:\n"
        "# AsynIPConfigure({{name}}, {{port}}, {{stop}}, {{parity}}, {{bits}}) \n"
        "AsynIPConfigure(asyn1, 10.0.1.1, 1, none, 8)\n"
        "asynSetOption(9600, 0, N, Y)\n"
        'asynOctetSetInputEos("\\n")\n'
        'asynOctetSetOutputEos("\\n")\n'
        "# Setting up Asyn Port asyn2 on 10.0.1.2:\n"
        "AsynIPConfigure(asyn2, 10.0.1.2, 1, none, 8)\n"
        "asynSetOption(9600, 0, N, Y)\n"
        'asynOctetSetInputEos("\\n")\n'
        'asynOctetSetOutputEos("\\n")\n'
    )


def test_obj_ref_script(motor_classes):
    asyn_def = find_entity_class(motor_classes, "asyn.AsynIP")
    motor_def = find_entity_class(motor_classes, "motorSim.simMotorController")

    asyn_def(name="asyn1", port="10.0.1.1", type="asyn.AsynIP")
    motor_obj = motor_def(
        port="asyn1",
        controllerName="ctrl1",
        P="IBEK-MO-01:",
        numAxes=4,
        type="motorSim.simMotorController",
    )

    render = Render()
    script_txt = render.render_script(motor_obj, motor_obj._model.pre_init)

    assert script_txt == (
        "# motorSimCreateController(controller_asyn_port_name, axis_count)\n"
        "# testing escaping:  {{enclosed in escaped curly braces}} \n"
        "motorSimCreateController(ctrl1, 4)\n"
    )


def test_database_render(motor_classes):
    asyn_def = find_entity_class(motor_classes, "asyn.AsynIP")
    sim_def = find_entity_class(motor_classes, "motorSim.simMotorController")
    motor_def = find_entity_class(motor_classes, "motorSim.simMotorAxis")

    asyn1 = asyn_def(name="asyn1", port="10.0.1.1", type="asyn.AsynIP")
    # TODO removing DESC below causes a failure in jinja templating
    # The default DESC field contains jinja escaping and this fails for some
    # reason. But it works fine in the test test_build_runtime_motorSim which
    # is what really counts I guess.
    sim_motor = sim_def(
        port="asyn1",
        controllerName="ctrl1",
        P="IBEK-MO-01:",
        numAxes=4,
        DESC="test",
        type="motorSim.simMotorController",
    )
    motor1 = motor_def(controller="ctrl1", M="M1", ADDR=1, type="motorSim.simMotorAxis")
    motor2 = motor_def(
        controller="ctrl1",
        M="M2",
        ADDR=2,
        is_cs=True,
        type="motorSim.simMotorAxis",
    )

    # make a dummy IOC with two entities as database render works against
    # a whole IOC rather than a single entity at a time.
    entities = [asyn1, sim_motor, motor1, motor2]

    render_db = RenderDb(entities)
    templates = render_db.render_database()

    assert templates == {
        "basic_asyn_motor.db": [
            '"P",           "M",  "DTYP",      "PORT",  "ADDR", "DESC",    "EGU",     "DIR", "VELO", "VMAX", "MRES", "DHLM",  "DLLM",   "INIT"',
            '"IBEK-MO-01:", "M1", "asynMotor", "ctrl1", "1",    "Motor 1", "degrees", "0",   "10.0", "10.0", ".01",  "20000", "-20000", ""    ',
        ],
        "basic_cs_asyn_motor.db": [
            '"P",           "CS_NUM", "DTYP",      "PORT",  "ADDR", "DESC",    "EGU",     "DIR", "VELO", "VMAX", "MRES", "DHLM",  "DLLM",   "INIT"',
            '"IBEK-MO-01:", "0",      "asynMotor", "ctrl1", "2",    "Motor 2", "degrees", "0",   "10.0", "10.0", ".01",  "20000", "-20000", ""    ',
        ],
        "sim_motor.db": [
            '"controllerName", "P",           "DESC"',
            '"ctrl1",          "IBEK-MO-01:", "test"',
        ],
    }


def test_environment_variables(motor_classes):
    asyn_def = find_entity_class(motor_classes, "asyn.AsynIP")

    asyn_obj = asyn_def(name="asyn1", port="10.0.1.1", type="asyn.AsynIP")

    render = Render()
    env_text = render.render_environment_variables(asyn_obj)

    assert env_text == "epicsEnvSet NAME_AS_ENV_VAR my name is asyn1\n"
