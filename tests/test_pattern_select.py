"""
Tests for narrowing a vendored pattern with ``select.only`` / ``select.models``
(``ibek pattern add --only`` / ``--model``) and the version 4 lock that records
them.
"""

import shutil
import warnings
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from ibek.__main__ import cli
from ibek.globals import GLOBALS, RUNTIME_LOCK_NAME
from ibek.pattern_cmds import lock as lock_module
from ibek.pattern_cmds import vendor
from ibek.pattern_cmds.lock import (
    SELECT_ONLY_LOCK_VERSION,
    RuntimeLock,
    Selection,
    SelectRule,
    file_hash,
)
from ibek.pattern_cmds.manifest import ManifestError
from ibek.pattern_cmds.sources import PatternError
from ibek.runtime_cmds import commands as runtime_commands
from tests.test_pattern import make_instance, make_pattern, tree

runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_schema_env(monkeypatch):
    """Keep a developer's or CI job's tokens and overrides out of every test."""
    for name in (
        "IBEK_SCHEMA_URL",
        "IBEK_GITLAB_HOSTS",
        "GITLAB_TOKEN",
        "CI_JOB_TOKEN",
        "CI_SERVER_HOST",
    ):
        monkeypatch.delenv(name, raising=False)


MULTI_SUPPORT = """\
module: multidev

entity_models:
  - name: alpha
    description: loads alpha.template
    parameters:
      P:
        type: str
        description: pv prefix
    databases:
      - file: alpha.template
        args:
          P:

  - name: beta
    description: loads beta.template by a path
    parameters:
      P:
        type: str
        description: pv prefix
    databases:
      - file: $(MULTIDEV)/db/beta.template
        args:
          P:

  - name: gamma
    description: loads gamma.template and instantiates an alpha
    parameters:
      P:
        type: str
        description: pv prefix
    databases:
      - file: gamma.template
        args:
          P:
    sub_entities:
      - type: multidev.alpha
        P: "{{P}}:A"

  - name: imaged
    description: loads a template from a support module in the image
    parameters:
      P:
        type: str
        description: pv prefix
    databases:
      - file: $(ADCORE)/db/NDStats.template
        args:
          P:

  - name: templated
    description: loads a template whose name is an expression
    parameters:
      P:
        type: str
        description: pv prefix
    databases:
      - file: "{{P}}.template"
        args:
          P:
"""

MULTI_MANIFEST = (
    "version: 1\n"
    "vendor:\n"
    "  - src: '[^/]+\\.(template|proto|ibek\\.support\\.yaml)'\n"
    "    dest: config\n"
)

MULTI_FILES = {
    "multidev.ibek.support.yaml": MULTI_SUPPORT,
    "multidev.proto": 'Terminator = CR;\nget { out "X?"; in "%f"; }\n',
    "alpha.template": "record(ai, $(P)A) {}\n",
    "beta.template": "record(ai, $(P)B) {}\n",
    "gamma.template": "record(ai, $(P)G) {}\n",
    "sim/multidev_sim.template": "record(ai, $(P)SIM) {}\n",
    "README.md": "docs\n",
}

SUPPORT_KEY = "config/multidev.ibek.support.yaml"
PROTO_KEY = "config/multidev.proto"


@pytest.fixture
def multi_library(tmp_path: Path) -> Path:
    """A pattern with several models, a protocol and files its manifest leaves."""
    return make_pattern(tmp_path / "lib", "multidev", MULTI_FILES, MULTI_MANIFEST)


def add(instance: Path, library: Path, select: Selection | None) -> None:
    vendor.add("multidev@1.0.0", instance, source_override=str(library), select=select)


def locked_files(instance: Path) -> set[str]:
    return set(RuntimeLock(instance / RUNTIME_LOCK_NAME).patterns["multidev"].files)


def cli_add(instance: Path, library: Path, *options: str):
    return runner.invoke(
        cli,
        ["pattern", "add", "multidev@1.0.0", str(instance), "--source", str(library)]
        + list(options),
    )


# --------------------------------------------------------------------------- #
# what each option vendors
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "select, expected",
    [
        (
            Selection(models=["alpha"]),
            {"config/alpha.template", PROTO_KEY},
        ),
        (
            # a database file given by a path matches the pattern file by name
            Selection(models=["beta"]),
            {"config/beta.template", PROTO_KEY},
        ),
        (
            # a model's sub-entities of the same pattern bring their files
            Selection(models=["gamma"]),
            {"config/gamma.template", "config/alpha.template", PROTO_KEY},
        ),
        (
            # a database file the pattern does not hold is left to the image
            Selection(models=["imaged"]),
            {PROTO_KEY},
        ),
        (
            Selection(only=["beta.template"]),
            {"config/beta.template"},
        ),
        (
            Selection(only=["multidev.proto", "beta.template"]),
            {"config/beta.template", PROTO_KEY},
        ),
        (
            # --only and --model combine to their union
            Selection(only=["beta.template"], models=["alpha"]),
            {"config/alpha.template", "config/beta.template", PROTO_KEY},
        ),
        (
            # --include still adds files, at the destination it names
            Selection(
                include=[SelectRule(src="sim/(.*_sim\\.template)", dest="config/\\1")],
                only=["beta.template"],
            ),
            {"config/beta.template", "config/multidev_sim.template"},
        ),
    ],
)
def test_narrowed_file_set(
    tmp_path: Path, multi_library: Path, select: Selection, expected: set[str]
):
    instance = make_instance(tmp_path)
    add(instance, multi_library, select)

    # the support YAML is always vendored, whole and unmodified
    assert locked_files(instance) == expected | {SUPPORT_KEY}
    assert (instance / SUPPORT_KEY).read_text() == MULTI_SUPPORT
    assert tree(instance / "config") == {"ioc.yaml"} | {
        key.removeprefix("config/") for key in expected | {SUPPORT_KEY}
    }
    assert vendor.check(instance).ok


def test_model_vendors_protocols_of_a_pattern_without_manifest(tmp_path: Path):
    """With no manifest every file is vendorable, so every protocol is kept."""
    files = {k: v for k, v in MULTI_FILES.items() if not k.startswith("sim/")}
    files["other.protocol"] = "Terminator = LF;\n"
    library = make_pattern(tmp_path / "lib", "multidev", files)
    instance = make_instance(tmp_path)
    add(instance, library, Selection(models=["alpha"]))
    assert locked_files(instance) == {
        SUPPORT_KEY,
        "config/alpha.template",
        PROTO_KEY,
        "config/other.protocol",
    }


def test_narrowing_keeps_manifest_destinations(tmp_path: Path):
    """A kept file lands where the manifest routes it."""
    manifest = (
        "version: 1\n"
        "vendor:\n"
        "  - src: '[^/]+\\.ibek\\.support\\.yaml'\n"
        "    dest: config\n"
        "  - src: '[^/]+\\.template'\n"
        "    dest: config/db/\n"
        "  - src: '[^/]+\\.proto'\n"
        "    dest: config/protocol/\n"
    )
    library = make_pattern(tmp_path / "lib", "multidev", MULTI_FILES, manifest)
    instance = make_instance(tmp_path)
    add(instance, library, Selection(models=["alpha"]))
    assert locked_files(instance) == {
        SUPPORT_KEY,
        "config/db/alpha.template",
        "config/protocol/multidev.proto",
    }


# --------------------------------------------------------------------------- #
# refusals
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "select, fragments",
    [
        (
            Selection(models=["alpha", "nosuch"]),
            [
                "no entity model 'nosuch'",
                "its models are: alpha, beta, gamma, imaged, templated",
            ],
        ),
        (
            Selection(only=["nosuch.template"]),
            [
                "'nosuch.template' is not a file this pattern vendors",
                "it vendors: alpha.template, beta.template, gamma.template, "
                "multidev.ibek.support.yaml, multidev.proto",
            ],
        ),
        (
            # a file the manifest leaves out is not vendorable by --only
            Selection(only=["README.md"]),
            ["'README.md' is not a file this pattern vendors", "--include"],
        ),
        (
            Selection(models=["templated"]),
            ["'{{P}}.template', which is a template expression", "--only"],
        ),
    ],
)
def test_narrowing_rejects(
    tmp_path: Path, multi_library: Path, select: Selection, fragments: list[str]
):
    instance = make_instance(tmp_path)
    with pytest.raises(ManifestError) as exc:
        add(instance, multi_library, select)
    for fragment in fragments:
        assert fragment in str(exc.value)
    assert not (instance / RUNTIME_LOCK_NAME).exists()
    assert tree(instance / "config") == {"ioc.yaml"}


@pytest.mark.parametrize(
    "options",
    [
        ["--only", "beta.template", "--exclude", "alpha\\.template"],
        ["--model", "alpha", "--exclude", "beta\\.template"],
    ],
)
def test_cli_refuses_exclude_with_only_or_model(
    tmp_path: Path, multi_library: Path, options: list[str]
):
    instance = make_instance(tmp_path)
    result = cli_add(instance, multi_library, *options)
    assert result.exit_code == 1
    assert not (instance / RUNTIME_LOCK_NAME).exists()


def test_selection_refuses_exclude_with_only_or_model():
    with pytest.raises(ValidationError, match="'exclude' cannot be combined"):
        Selection(exclude=["x"], only=["y"])
    with pytest.raises(ValidationError, match="'exclude' cannot be combined"):
        Selection(exclude=["x"], models=["y"])


def test_cli_add_with_only_and_model(tmp_path: Path, multi_library: Path):
    instance = make_instance(tmp_path)
    result = cli_add(
        instance,
        multi_library,
        "--model",
        "alpha",
        "--only",
        "beta.template",
        "--model",
        "alpha",  # a repeat is recorded once
    )
    assert result.exit_code == 0, result.output
    select = RuntimeLock(instance / RUNTIME_LOCK_NAME).patterns["multidev"].select
    assert select == Selection(only=["beta.template"], models=["alpha"])

    result = cli_add(instance, multi_library, "--model", "nosuch")
    assert result.exit_code == 1
    # the refused re-add left the instance as it was
    assert (
        select == RuntimeLock(instance / RUNTIME_LOCK_NAME).patterns["multidev"].select
    )


# --------------------------------------------------------------------------- #
# lock version 4
# --------------------------------------------------------------------------- #
def test_lock_version_4_round_trip(tmp_path: Path, multi_library: Path):
    instance = make_instance(tmp_path)
    lock_path = instance / RUNTIME_LOCK_NAME
    select = Selection(
        include=[SelectRule(src="sim/(.*_sim\\.template)", dest="config/\\1")],
        only=["beta.template"],
        models=["alpha"],
    )
    add(instance, multi_library, select)

    text = lock_path.read_text()
    assert text.startswith(f"version: {SELECT_ONLY_LOCK_VERSION}\n")
    assert (
        "    select:\n"
        "      include:\n"
        "      - src: sim/(.*_sim\\.template)\n"
        "        dest: config/\\1\n"
        "      only:\n"
        "      - beta.template\n"
        "      models:\n"
        "      - alpha\n"
        "    files:\n"
    ) in text
    reloaded = RuntimeLock(lock_path)
    assert reloaded.patterns["multidev"].select == select
    reloaded.save()
    assert lock_path.read_text() == text

    # re-adding without a narrowing writes the lowest version again
    add(instance, multi_library, None)
    assert lock_path.read_text().startswith("version: 1\n")


def lock_text(version: int, schema_url: str = "", select: str = "") -> str:
    return (
        f"version: {version}\n"
        + (f"schema_url: {schema_url}\n" if schema_url else "")
        + "patterns:\n"
        "  multidev:\n"
        "    version: 1.0.0\n"
        "    source: /lib\n" + select + "    files:\n"
        f"      config/alpha.template: {file_hash(b'a')}\n"
        f"      {SUPPORT_KEY}: {file_hash(b'b')}\n"
    )


SCHEMA_URL = "https://example.com/schemas/ioc.schema.json"
INCLUDE_SELECT = (
    "    select:\n"
    "      include:\n"
    "      - src: sim/(.*)\n"
    "        dest: config/\\1\n"
    "      exclude:\n"
    "      - beta\\.template\n"
)


@pytest.mark.parametrize(
    "text",
    [
        lock_text(1),
        lock_text(2, select=INCLUDE_SELECT),
        lock_text(3, schema_url=SCHEMA_URL),
        lock_text(3, schema_url=SCHEMA_URL, select=INCLUDE_SELECT),
    ],
)
def test_locks_below_version_4_are_rewritten_byte_identical(tmp_path: Path, text: str):
    path = tmp_path / RUNTIME_LOCK_NAME
    path.write_text(text)
    RuntimeLock(path).save()
    assert path.read_text() == text


@pytest.mark.parametrize("version", [2, 3])
@pytest.mark.parametrize(
    "select",
    ["    select:\n      only: [alpha.template]\n", "    select:\n      models: [x]\n"],
)
def test_lock_below_version_4_refuses_only_and_models(
    tmp_path: Path, version: int, select: str
):
    path = tmp_path / RUNTIME_LOCK_NAME
    path.write_text(lock_text(version, select=select))
    with pytest.raises(PatternError) as exc:
        RuntimeLock(path)
    assert (
        f"has a 'select.only' or 'select.models' but the lock is version {version}"
    ) in str(exc.value)


def test_lock_refuses_exclude_with_only(tmp_path: Path):
    path = tmp_path / RUNTIME_LOCK_NAME
    path.write_text(
        lock_text(4, select="    select:\n      exclude: [x]\n      only: [y]\n")
    )
    with pytest.raises(PatternError, match="'exclude' cannot be combined"):
        RuntimeLock(path)


def test_version_4_lock_is_refused_by_a_version_3_reader(
    tmp_path: Path, multi_library: Path, monkeypatch
):
    instance = make_instance(tmp_path)
    add(instance, multi_library, Selection(models=["alpha"]))
    monkeypatch.setattr(lock_module, "SUPPORTED_LOCK_VERSIONS", frozenset({1, 2, 3}))
    assert vendor.check(instance).failures == [
        f"{instance / RUNTIME_LOCK_NAME}: unsupported lock version 4 "
        "(this ibek reads: 1, 2, 3)"
    ]


# --------------------------------------------------------------------------- #
# update and restore
# --------------------------------------------------------------------------- #
def test_update_re_resolves_models(tmp_path: Path, multi_library: Path):
    """A model whose database file is renamed upstream still gets its file."""
    instance = make_instance(tmp_path)
    add(instance, multi_library, Selection(models=["alpha"]))
    assert "config/alpha.template" in locked_files(instance)

    pattern = multi_library / "multidev"
    (pattern / "alpha.template").rename(pattern / "alpha2.template")
    support = pattern / "multidev.ibek.support.yaml"
    support.write_text(
        support.read_text().replace("file: alpha.template", "file: alpha2.template")
    )

    vendor.update("multidev", instance)
    assert locked_files(instance) == {
        SUPPORT_KEY,
        "config/alpha2.template",
        PROTO_KEY,
    }
    assert not (instance / "config" / "alpha.template").exists()  # pruned
    assert RuntimeLock(instance / RUNTIME_LOCK_NAME).patterns[
        "multidev"
    ].select == Selection(models=["alpha"])
    assert vendor.check(instance).ok


def test_update_keeps_only_literal(tmp_path: Path, multi_library: Path):
    instance = make_instance(tmp_path)
    add(instance, multi_library, Selection(only=["beta.template"]))
    before = (instance / RUNTIME_LOCK_NAME).read_text()

    (multi_library / "multidev" / "beta.template").unlink()
    with pytest.raises(ManifestError, match="'beta.template' is not a file"):
        vendor.update("multidev", instance)
    assert (instance / RUNTIME_LOCK_NAME).read_text() == before
    assert vendor.check(instance).ok


def test_restore_reapplies_only_and_models(tmp_path: Path, multi_library: Path):
    instance = make_instance(tmp_path)
    add(instance, multi_library, Selection(only=["beta.template"], models=["alpha"]))
    before = (instance / RUNTIME_LOCK_NAME).read_text()
    before_tree = tree(instance)

    alpha = instance / "config" / "alpha.template"
    alpha.write_text("edited\n")
    (instance / "config" / "beta.template").unlink()
    assert not vendor.check(instance).ok

    vendor.restore("multidev", instance)
    assert alpha.read_text() == MULTI_FILES["alpha.template"]
    assert tree(instance) == before_tree
    assert (instance / RUNTIME_LOCK_NAME).read_text() == before
    assert vendor.check(instance).ok


# --------------------------------------------------------------------------- #
# generate2: an entity whose model files were not vendored
# --------------------------------------------------------------------------- #
def generate2(instance: Path, tmp_path: Path, entity_type: str):
    (instance / "config" / "ioc.yaml").write_text(
        "ioc_name: test\n"
        "description: test\n"
        "entities:\n"
        f"  - type: {entity_type}\n"
        "    P: 'X:'\n"
    )
    return runner.invoke(
        cli,
        [
            "runtime",
            "generate2",
            str(instance / "config"),
            "--definitions",
            str(instance / SUPPORT_KEY),
            "--output",
            str(tmp_path / "out"),
            "--no-pvi",
        ],
    )


def test_generate2_reports_a_model_whose_files_were_not_vendored(
    tmp_path: Path, multi_library: Path
):
    instance = make_instance(tmp_path)
    add(instance, multi_library, Selection(models=["alpha"]))

    result = generate2(instance, tmp_path, "multidev.alpha")
    assert result.exit_code == 0, result.output

    shutil.rmtree(tmp_path / "out")
    result = generate2(instance, tmp_path, "multidev.gamma")
    assert result.exit_code == 1
    assert (
        "entity multidev.gamma uses model gamma whose files were not vendored "
        "from pattern multidev (gamma.template is missing); re-add with "
        "`ibek pattern add <library>:multidev@1.0.0 <instance> --model gamma`"
    ) in result.output
    assert not (tmp_path / "out").exists()  # refused before anything is written

    # a database file given by a path is a support module's, in the image
    for model in "beta", "imaged":
        result = generate2(instance, tmp_path, f"multidev.{model}")
        assert result.exit_code == 0, result.output


def test_generate2_without_a_narrowed_lock_is_unchecked(
    tmp_path: Path, multi_library: Path
):
    instance = make_instance(tmp_path)
    add(instance, multi_library, None)
    (instance / "config" / "beta.template").unlink()
    result = generate2(instance, tmp_path, "multidev.beta")
    assert result.exit_code == 0, result.output


def test_generate2_skips_a_lock_it_cannot_read(
    tmp_path: Path, multi_library: Path, monkeypatch
):
    """`ibek pattern check` reports an unreadable lock; generate2 only warns."""
    instance = make_instance(tmp_path)
    add(instance, multi_library, Selection(models=["alpha"]))
    lock_path = instance / RUNTIME_LOCK_NAME

    def unreadable(path):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(runtime_commands, "RuntimeLock", unreadable)
    result = generate2(instance, tmp_path, "multidev.gamma")
    assert result.exit_code == 0, result.output
    assert "vendored model files not checked" in result.output
    monkeypatch.undo()

    lock_path.write_text("multidev:\n  version: 1.0.0\n")  # another format
    result = generate2(instance, tmp_path, "multidev.gamma")
    assert result.exit_code == 0, result.output
    assert "lock format not recognised" in result.output


def test_ambiguous_database_basename_is_refused(tmp_path: Path):
    files = dict(MULTI_FILES)
    files["multidev.ibek.support.yaml"] = MULTI_SUPPORT.replace(
        "file: alpha.template", "file: $(MULTIDEV)/db/alpha.template"
    )
    files["sub/alpha.template"] = "record(ai, $(P)A2) {}\n"
    library = make_pattern(tmp_path / "lib", "multidev", files)  # no manifest
    instance = make_instance(tmp_path)
    with pytest.raises(ManifestError) as exc:
        add(instance, library, Selection(models=["alpha"]))
    assert "matches several pattern files (alpha.template, sub/alpha.template)" in (
        str(exc.value)
    )
    assert not (instance / RUNTIME_LOCK_NAME).exists()


# --------------------------------------------------------------------------- #
# pvi device files and autosave request files follow their models
# --------------------------------------------------------------------------- #
PVI_SUPPORT = """\
module: pvidev

entity_models:
  - name: controller
    description: a controller with a pvi device and an optional extra template
    parameters:
      P:
        type: str
        description: pv prefix
      EXTRA:
        type: bool
        description: load extra.template
        default: false
    databases:
      - file: controller.template
        args:
          P:
      - file: extra.template
        enabled: "{{EXTRA}}"
        args:
          P:
    pvi:
      yaml_path: controller.pvi.device.yaml
      ui_index: true
      ui_macros:
        P:

  - name: pump
    description: a pump with a pvi device
    parameters:
      P:
        type: str
        description: pv prefix
    databases:
      - file: pump.template
        args:
          P:
    pvi:
      yaml_path: pump.pvi.device.yaml
      ui_macros:
        P:
"""


def pvi_device(label: str) -> str:
    return (
        f"label: {label}\n"
        "children:\n"
        "  - type: SignalR\n"
        "    name: Value\n"
        "    read_pv: $(P)VALUE\n"
        "    read_widget:\n"
        "      type: TextRead\n"
    )


PVI_FILES = {
    "pvidev.ibek.support.yaml": PVI_SUPPORT,
    "pvidev.proto": "Terminator = CR;\n",
    "controller.template": "record(ai, $(P)C) {}\n",
    "extra.template": "record(ai, $(P)E) {}\n",
    "pump.template": "record(ai, $(P)P) {}\n",
    "controller_settings.req": "$(P)C\n",
    "controller_positions.req": "$(P)C\n",
    "pump_settings.req": "$(P)P\n",
    "controller.pvi.device.yaml": pvi_device("Controller"),
    "pump.pvi.device.yaml": pvi_device("Pump"),
    "README.md": "docs\n",
}

PVI_MANIFEST = (
    "version: 1\n"
    "vendor:\n"
    "  - src: '[^/]+\\.(template|proto|req|ibek\\.support\\.yaml"
    "|pvi\\.device\\.yaml)'\n"
    "    dest: config\n"
)


@pytest.fixture
def pvi_library(tmp_path: Path) -> Path:
    return make_pattern(tmp_path / "lib", "pvidev", PVI_FILES, PVI_MANIFEST)


def test_model_keeps_its_pvi_device_and_req_files(tmp_path: Path, pvi_library: Path):
    instance = make_instance(tmp_path)
    vendor.add(
        "pvidev@1.0.0",
        instance,
        source_override=str(pvi_library),
        select=Selection(models=["controller"]),
    )
    files = set(RuntimeLock(instance / RUNTIME_LOCK_NAME).patterns["pvidev"].files)
    assert files == {
        "config/pvidev.ibek.support.yaml",
        "config/pvidev.proto",
        "config/controller.template",
        "config/extra.template",
        "config/controller_settings.req",
        "config/controller_positions.req",
        "config/controller.pvi.device.yaml",
    }


def pvi_generate2(instance: Path, out: Path, entity: str, *options: str, **params: str):
    """Run generate2 on ``instance`` (the image's IOC folder) with pvi on."""
    lines = "".join(f"    {key}: {value}\n" for key, value in params.items())
    (instance / "config" / "ioc.yaml").write_text(
        "ioc_name: test\n"
        "description: test\n"
        "entities:\n"
        f"  - type: pvidev.{entity}\n"
        "    P: 'X:'\n" + lines
    )
    shutil.rmtree(out, ignore_errors=True)
    with warnings.catch_warnings():
        # pvi's Device.deserialize_parents warns that `parent` is deprecated
        warnings.simplefilter("ignore", DeprecationWarning)
        return runner.invoke(
            cli,
            [
                "runtime",
                "generate2",
                str(instance / "config"),
                "--definitions",
                str(instance / "config" / "pvidev.ibek.support.yaml"),
                "--output",
                str(out),
                *options,
            ],
        )


def test_generate2_with_pvi_on_a_model_with_pvi(
    tmp_epics_root: Path, tmp_path: Path, pvi_library: Path
):
    """pvi generation reads the vendored pvi device file from the config folder."""
    instance = GLOBALS.IOC_FOLDER
    out = tmp_path / "out"
    vendor.add(
        "pvidev@1.0.0",
        instance,
        source_override=str(pvi_library),
        select=Selection(models=["controller"]),
    )
    result = pvi_generate2(instance, out, "controller")
    assert result.exit_code == 0, result.output
    assert (GLOBALS.OPI_OUTPUT / "controller.pvi.bob").is_file()

    # a disabled entity's database files are not checked ...
    result = pvi_generate2(instance, out, "pump", "--no-pvi", entity_enabled="false")
    assert result.exit_code == 0, result.output
    # ... but pvi generation reads its pvi device file
    result = pvi_generate2(instance, out, "pump", entity_enabled="false")
    assert result.exit_code == 1
    assert "(pump.pvi.device.yaml is missing)" in result.output
    assert "(pump.template is missing)" not in result.output

    result = pvi_generate2(instance, out, "pump")
    assert result.exit_code == 1
    assert (
        "entity pvidev.pump uses model pump whose files were not vendored from "
        "pattern pvidev (pump.template is missing)"
    ) in result.output
    assert "(pump.pvi.device.yaml is missing)" in result.output


def test_generate2_checks_pvi_files_only_with_pvi(
    tmp_epics_root: Path, tmp_path: Path, pvi_library: Path
):
    instance = GLOBALS.IOC_FOLDER
    out = tmp_path / "out"
    vendor.add(
        "pvidev@1.0.0",
        instance,
        source_override=str(pvi_library),
        select=Selection(only=["controller.template"]),
    )
    result = pvi_generate2(instance, out, "controller")
    assert result.exit_code == 1
    assert "(controller.pvi.device.yaml is missing)" in result.output

    # extra.template is disabled by default, so only the pvi file was missing
    result = pvi_generate2(instance, out, "controller", "--no-pvi")
    assert result.exit_code == 0, result.output

    result = pvi_generate2(instance, out, "controller", "--no-pvi", EXTRA="true")
    assert result.exit_code == 1
    assert "(extra.template is missing)" in result.output


def psu_support(models: list[str]) -> str:
    """A support YAML for module ODPsu defining ``models``, one template each."""
    text = "module: ODPsu\n\nentity_models:\n"
    for model in models:
        text += (
            f"  - name: {model}\n"
            f"    description: loads {model}.template\n"
            "    parameters:\n"
            "      P:\n"
            "        type: str\n"
            "        description: pv prefix\n"
            "    databases:\n"
            f"      - file: {model}.template\n"
            "        args:\n"
            "          P:\n"
        )
    return text


def test_generate2_one_module_from_two_narrowed_patterns(tmp_path: Path):
    """Two narrowed patterns may declare one module; each vendors its own model."""
    library = tmp_path / "lib"
    make_pattern(
        library,
        "ODPsu",
        {
            "ODPsu.ibek.support.yaml": psu_support(["psuA", "psuC"]),
            "psuA.template": "record(ai, $(P)A) {}\n",
            "psuC.template": "record(ai, $(P)C) {}\n",
        },
    )
    make_pattern(
        library,
        "ODPsu2",
        {
            "ODPsu2.ibek.support.yaml": psu_support(["psuB"]),
            "psuB.template": "record(ai, $(P)B) {}\n",
        },
    )
    instance = make_instance(tmp_path)
    for name, model in ("ODPsu", "psuA"), ("ODPsu2", "psuB"):
        vendor.add(
            f"{name}@1.0.0",
            instance,
            source_override=str(library),
            select=Selection(models=[model]),
        )

    def run(model: str):
        (instance / "config" / "ioc.yaml").write_text(
            "ioc_name: test\n"
            "description: test\n"
            "entities:\n"
            f"  - type: ODPsu.{model}\n"
            "    P: 'X:'\n"
        )
        return runner.invoke(
            cli,
            [
                "runtime",
                "generate2",
                str(instance / "config"),
                "--definitions",
                str(instance / "config" / "ODPsu.ibek.support.yaml"),
                "--definitions",
                str(instance / "config" / "ODPsu2.ibek.support.yaml"),
                "--output",
                str(tmp_path / "out"),
                "--no-pvi",
            ],
        )

    for model in "psuA", "psuB":
        result = run(model)
        assert result.exit_code == 0, result.output
    result = run("psuC")
    assert result.exit_code == 1
    assert (
        "entity ODPsu.psuC uses model psuC whose files were not vendored from "
        "pattern ODPsu or ODPsu2 (psuC.template is missing)"
    ) in result.output


def two_module_support(module: str, models: dict[str, list[str]]) -> str:
    """A support YAML for ``module``: each model loads ``<module>_<model>.template``
    and instantiates the given sub-entity types."""
    text = f"module: {module}\n\nentity_models:\n"
    for model, subs in models.items():
        text += (
            f"  - name: {model}\n"
            "    description: test\n"
            "    databases:\n"
            f"      - file: {module}_{model}.template\n"
            "        args: {}\n"
        )
        if subs:
            text += "    sub_entities:\n" + "".join(
                f"      - type: {t}\n" for t in subs
            )
    return text


@pytest.fixture
def two_module_library(tmp_path: Path) -> Path:
    """One pattern whose two support YAMLs both define a model named Child."""
    return make_pattern(
        tmp_path / "lib",
        "twomod",
        {
            "a.ibek.support.yaml": two_module_support(
                "a", {"Parent": ["a.Child"], "Child": []}
            ),
            "b.ibek.support.yaml": two_module_support("b", {"Child": []}),
            "a_Parent.template": "",
            "a_Child.template": "",
            "b_Child.template": "",
        },
    )


@pytest.mark.parametrize(
    "models, expected",
    [
        (["Parent"], {"config/a_Parent.template", "config/a_Child.template"}),
        (["b.Child"], {"config/b_Child.template"}),
        (["a.Child"], {"config/a_Child.template"}),
    ],
)
def test_models_keep_their_module(
    tmp_path: Path, two_module_library: Path, models: list[str], expected: set[str]
):
    instance = make_instance(tmp_path)
    vendor.add(
        "twomod@1.0.0",
        instance,
        source_override=str(two_module_library),
        select=Selection(models=models),
    )
    files = set(RuntimeLock(instance / RUNTIME_LOCK_NAME).patterns["twomod"].files)
    assert files == expected | {
        "config/a.ibek.support.yaml",
        "config/b.ibek.support.yaml",
    }


def test_model_name_of_two_modules_is_refused(tmp_path: Path, two_module_library: Path):
    instance = make_instance(tmp_path)
    with pytest.raises(ManifestError) as exc:
        vendor.add(
            "twomod@1.0.0",
            instance,
            source_override=str(two_module_library),
            select=Selection(models=["Child"]),
        )
    assert "'Child' names models of several modules (a.Child, b.Child)" in str(
        exc.value
    )
    with pytest.raises(ManifestError) as exc:
        vendor.add(
            "twomod@1.0.0",
            instance,
            source_override=str(two_module_library),
            select=Selection(models=["Nope"]),
        )
    assert "its models are: a.Child, a.Parent, b.Child" in str(exc.value)
