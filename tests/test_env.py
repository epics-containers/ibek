"""Process environment access without changing existing template contexts."""

import pytest

from ibek import gen_scripts
from ibek.utils import UTILS, Utils, make_template


@pytest.mark.parametrize(
    "expression",
    [
        "env.IBEK_TEST_VALUE",
        "env['IBEK_TEST_VALUE']",
        "_global.get_env('IBEK_TEST_VALUE')",
    ],
)
def test_environment_access(monkeypatch, expression):
    monkeypatch.setenv("IBEK_TEST_VALUE", "first")
    utils = Utils()
    assert utils.render({}, "{{ " + expression + " }}") == "first"
    monkeypatch.setenv("IBEK_TEST_VALUE", "second")
    assert utils.render({}, "{{ " + expression + " }}") == "second"


def test_missing_and_empty_environment(monkeypatch):
    monkeypatch.delenv("IBEK_TEST_VALUE", raising=False)
    utils = Utils()
    for expression in ("env.IBEK_TEST_VALUE", "env['IBEK_TEST_VALUE']"):
        with pytest.raises(ValueError, match="IBEK_TEST_VALUE"):
            utils.render({}, "{{ " + expression + " }}")
    assert (
        utils.render({}, "{{ env.get('IBEK_TEST_VALUE', 'fallback') }}") == "fallback"
    )
    assert utils.render({}, "{{ _global.get_env('IBEK_TEST_VALUE') }}") == ""
    monkeypatch.setenv("IBEK_TEST_VALUE", "")
    assert utils.render({}, "{{ env.get('IBEK_TEST_VALUE', 'fallback') }}") == ""


def test_existing_env_names_take_precedence(monkeypatch):
    monkeypatch.setenv("IBEK_TEST_VALUE", "process")
    utils = Utils()
    assert utils.render({"env": "parameter"}, "{{ env }}") == "parameter"
    utils.set("env", "shared")
    assert utils.render({}, "{{ env }}") == "shared"
    assert utils.render({"env": "parameter"}, "{{ env }}") == "shared"
    assert utils.render({}, "{{ _global.get_env('IBEK_TEST_VALUE') }}") == "process"


def test_mapping_method_names_and_read_only_access(monkeypatch):
    monkeypatch.setenv("get", "value")
    utils = Utils()
    assert utils.render({}, "{{ env['get'] }}") == "value"
    with pytest.raises(ValueError, match="update"):
        utils.render({}, "{{ env.update({'get': 'changed'}) }}")
    assert utils.render({}, "{{ env['get'] }}") == "value"


def test_environment_in_database_args(monkeypatch):
    monkeypatch.setenv("IBEK_TEST_VALUE", "42")
    utils = Utils()
    assert utils.render_map({}, {"env": "{{ env.IBEK_TEST_VALUE }}"}) == {"env": "42"}
    assert utils.render_map({"env": "macro value"}, {"env": None}) == {
        "env": "macro value"
    }
    assert utils.render({}, "{{ env.IBEK_TEST_VALUE }}", "int") == 42
    assert utils.render({}, "$(env)") == "$(env)"


def test_environment_in_assembly_templates(monkeypatch, tmp_path):
    monkeypatch.setenv("IBEK_TEST_VALUE", "process")
    monkeypatch.setattr(UTILS, "variables", {})
    monkeypatch.setattr(gen_scripts, "TEMPLATES", tmp_path)
    (tmp_path / "st.cmd.jinja").write_text("{{ env.IBEK_TEST_VALUE }}")
    (tmp_path / "ioc.subst.jinja").write_text("{{ env.IBEK_TEST_VALUE }}")
    assert gen_scripts.create_boot_script([]) == "process"
    assert gen_scripts.create_db_script([], []) == "process"

    UTILS.set("env", {"IBEK_TEST_VALUE": "shared"})
    assert gen_scripts.create_boot_script([]) == "shared"
    UTILS.variables.clear()
    monkeypatch.delenv("IBEK_TEST_VALUE")
    for name in ("st.cmd.jinja", "ioc.subst.jinja"):
        (tmp_path / name).write_text("{{ env.IBEK_TEST_VALUE }}:{{ missing }}")
    assert gen_scripts.create_boot_script([]) == ":"
    assert gen_scripts.create_db_script([], []) == ":"


def test_compiled_template_reads_current_environment(monkeypatch):
    template = make_template("{{ env.IBEK_TEST_VALUE }}")
    monkeypatch.setenv("IBEK_TEST_VALUE", "first")
    assert template.render() == "first"
    monkeypatch.setenv("IBEK_TEST_VALUE", "second")
    assert template.render() == "second"
