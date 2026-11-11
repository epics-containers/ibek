"""
Tests for ``ibek pattern install``: runtime patterns installed into an image.
"""

import os
import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from ibek.__main__ import cli
from ibek.globals import GLOBALS, IMAGE_LOCK_NAME
from ibek.ioc_cmds.assets import extract_assets
from ibek.pattern_cmds import install as install_module
from ibek.pattern_cmds.lock import file_hash
from ibek.runtime_cmds.commands import warn_shadowed_modules

runner = CliRunner()


def support_yaml(module: str | None) -> str:
    head = f"module: {module}\n" if module is not None else ""
    return (
        head + "entity_models:\n"
        "  - name: dev\n"
        "    description: a test device\n"
        "    parameters: {}\n"
    )


MANIFEST = """\
version: 1
vendor:
  - src: '.*\\.(ibek\\.support\\.yaml|pvi\\.device\\.yaml|proto|template|req)'
    dest: config
"""


def make_pattern(library: Path, name: str, files: dict[str, str]) -> Path:
    pattern = library / name
    for rel, text in files.items():
        target = pattern / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return library


def device_files(name: str) -> dict[str, str]:
    """A pattern's files: one of every type install routes, plus documentation."""
    return {
        f"{name}.ibek.support.yaml": support_yaml(name),
        f"{name}.pvi.device.yaml": "label: dev\n",
        f"{name}.proto": "Terminator = CR;\n",
        f"db/{name}.template": "record(ai, $(P)X) {}\n",
        f"db/{name}_settings.req": "$(P)X\n",
        "README.md": "documentation, not installed\n",
        "ibek.manifest.yaml": MANIFEST,
    }


def snapshot(root: Path) -> dict[str, bytes | str]:
    """Every file and link under ``root``, with its content or link target."""
    result: dict[str, bytes | str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[rel] = f"-> {os.readlink(path)}"
        elif path.is_file():
            result[rel] = path.read_bytes()
    return result


@pytest.fixture
def run(caplog):
    """Run ``ibek pattern <args>``; return its exit code and its output + log.

    Errors are logged rather than echoed, so the log is returned with the output.
    """

    def invoke(*args) -> tuple[int, str]:
        caplog.clear()
        result = runner.invoke(cli, ["pattern", *[str(arg) for arg in args]])
        return result.exit_code, result.output + caplog.text

    return invoke


@pytest.fixture
def library(tmp_path: Path) -> Path:
    lib = tmp_path / "lib"
    make_pattern(lib, "dev", device_files("dev"))
    make_pattern(lib, "other", device_files("other"))
    return lib


@pytest.fixture(autouse=True)
def _no_library_env(monkeypatch):
    monkeypatch.delenv("IBEK_PATTERN_LIBRARIES", raising=False)
    monkeypatch.delenv("IBEK_ALLOW_DIRTY", raising=False)


def read_lock() -> dict:
    return YAML(typ="safe").load(GLOBALS.IMAGE_PATTERN_LOCK)


# --------------------------------------------------------------------------- #
# install and check
# --------------------------------------------------------------------------- #
def test_install_routes_files_and_writes_lock(tmp_epics_root: Path, library: Path, run):
    code, output = run("install", "mylib:dev@1.0.0", "--source", library)
    assert code == 0, output
    assert "installed 1 pattern(s)" in output

    epics = tmp_epics_root
    installed = {
        "ibek-defs/dev.ibek.support.yaml",
        "pvi-defs/dev.pvi.device.yaml",
        "support/configure/protocol/dev.proto",
        "support/mylib/db/dev.template",
        "support/mylib/db/dev_settings.req",
    }
    for rel in installed:
        assert (epics / rel).is_file(), rel
    assert not list(epics.rglob("README.md"))

    lock = read_lock()
    assert GLOBALS.IMAGE_PATTERN_LOCK == epics / "ibek-defs" / IMAGE_LOCK_NAME
    assert lock["version"] == 1
    entry = lock["libraries"]["mylib"]["dev"]
    assert entry["verified"] is False
    assert entry["version"] == "1.0.0"
    assert entry["source"] == str(library)
    assert entry["commit"] is None
    assert entry["modules"] == ["dev"]
    assert set(entry["files"]) == installed
    for rel, digest in entry["files"].items():
        assert digest == file_hash((epics / rel).read_bytes())

    code, output = run("check", "--image")
    assert code == 0, output
    assert "installed patterns match the image lock" in output


def test_install_list_file(tmp_epics_root: Path, library: Path, tmp_path: Path, run):
    listing = tmp_path / "patterns.txt"
    listing.write_text("# vacuum devices\nmylib:dev@1.0.0\n\nmylib:other@1.0.0  # x\n")
    code, output = run("install", "--list", listing, "--source", library)
    assert code == 0, output
    assert set(read_lock()["libraries"]["mylib"]) == {"dev", "other"}


def test_check_image_reports_changes(tmp_epics_root: Path, library: Path, run):
    assert run("install", "mylib:dev@1.0.0", "--source", library)[0] == 0
    (tmp_epics_root / "support/configure/protocol/dev.proto").write_text("changed\n")
    (tmp_epics_root / "pvi-defs/dev.pvi.device.yaml").unlink()

    code, output = run("check", "--image")
    assert code == 1
    assert "dev.proto hash mismatch" in output
    assert "dev.pvi.device.yaml missing installed file" in output

    code, output = run("check", "--image", "--allow-dirty")
    assert code == 0, output
    assert "warning:" in output


def test_check_image_without_lock(tmp_epics_root: Path, run):
    code, output = run("check", "--image")
    assert code == 0, output
    assert "no image lock: nothing installed" in output


def test_check_image_refuses_bad_lock(tmp_epics_root: Path, run):
    GLOBALS.IMAGE_PATTERN_LOCK.write_text("version: 7\npatterns: {}\n")
    code, _ = run("check", "--image", "--allow-dirty")
    assert code == 1


def test_lock_refuses_escaping_key(tmp_epics_root: Path, run):
    GLOBALS.IMAGE_PATTERN_LOCK.write_text(
        "version: 1\nlibraries:\n  l:\n    dev:\n      version: '1'\n"
        "      source: s\n      verified: false\n      modules: [dev]\n"
        "      files:\n        ../etc/passwd: sha256:00\n"
    )
    code, _ = run("check", "--image")
    assert code == 1


def test_second_run_appends_and_refuses_reinstall(
    tmp_epics_root: Path, library: Path, run
):
    assert run("install", "mylib:dev@1.0.0", "--source", library)[0] == 0
    assert run("install", "mylib:other@1.0.0", "--source", library)[0] == 0
    assert set(read_lock()["libraries"]["mylib"]) == {"dev", "other"}

    before = snapshot(tmp_epics_root)
    code, output = run("install", "mylib:dev@1.0.0", "--source", library)
    assert code == 1
    assert "already installed" in output
    assert snapshot(tmp_epics_root) == before
    assert run("check", "--image")[0] == 0


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_install_from_git_records_commit_and_clones_once(
    tmp_epics_root: Path, library: Path, monkeypatch, run
):
    git(library, "init", "--quiet")
    git(library, "add", ".")
    git(library, "commit", "--quiet", "-m", "patterns")
    git(library, "tag", "1.0.0")
    commit = git(library, "rev-parse", "HEAD")

    # A local path is copied, not cloned; treat it as a remote to clone it.
    monkeypatch.setattr(install_module, "is_local", lambda uri: False)
    clones = []
    real_clone = install_module.clone_library

    def counting_clone(uri, version, dest):
        clones.append((uri, version))
        return real_clone(uri, version, dest)

    monkeypatch.setattr(install_module, "clone_library", counting_clone)
    monkeypatch.setenv("IBEK_PATTERN_LIBRARIES", f"mylib={library}")

    code, output = run("install", "mylib:dev@1.0.0", "mylib:other@1.0.0")
    assert code == 0, output
    assert clones == [(str(library), "1.0.0")]
    patterns = read_lock()["libraries"]["mylib"]
    assert patterns["dev"]["commit"] == commit
    assert patterns["other"]["commit"] == commit
    assert patterns["dev"]["verified"] is True


# --------------------------------------------------------------------------- #
# refusals: each writes nothing
# --------------------------------------------------------------------------- #
def _setup_module_in_image(epics: Path, library: Path) -> list[str]:
    (epics / "ibek-defs" / "compiled").mkdir()
    (epics / "ibek-defs" / "compiled" / "dev.ibek.support.yaml").write_text(
        support_yaml("dev")
    )
    return ["mylib:other@1", "mylib:dev@1"]


def _setup_existing_file(epics: Path, library: Path) -> list[str]:
    (epics / "support/configure/protocol").mkdir(parents=True)
    (epics / "support/configure/protocol/dev.proto").write_text("x\n")
    return ["mylib:dev@1"]


def _setup_shared_file(epics: Path, library: Path) -> list[str]:
    (library / "other" / "dev.proto").write_text("y\n")
    return ["mylib:dev@1", "mylib:other@1"]


def _setup_shared_module(epics: Path, library: Path) -> list[str]:
    (library / "other" / "other.ibek.support.yaml").write_text(support_yaml("dev"))
    return ["mylib:dev@1", "mylib:other@1"]


def _setup_same_name_twice_in_pattern(epics: Path, library: Path) -> list[str]:
    (library / "dev" / "db" / "dev.proto").write_text("y\n")
    return ["mylib:dev@1"]


def _setup_listed_twice(epics: Path, library: Path) -> list[str]:
    return ["mylib:dev@1", "mylib:dev@1"]


def _setup_selects_nothing(epics: Path, library: Path) -> list[str]:
    make_pattern(library, "empty", {"README.md": "x\n", "ibek.manifest.yaml": MANIFEST})
    return ["mylib:dev@1", "mylib:empty@1"]


def _setup_no_support_yaml(epics: Path, library: Path) -> list[str]:
    (library / "other" / "other.ibek.support.yaml").unlink()
    return ["mylib:dev@1", "mylib:other@1"]


def _setup_no_module(epics: Path, library: Path) -> list[str]:
    (library / "other" / "other.ibek.support.yaml").write_text(support_yaml(None))
    return ["mylib:dev@1", "mylib:other@1"]


def _setup_template_elsewhere(epics: Path, library: Path) -> list[str]:
    # the sample tree's ADSimDetector/db holds dummy.template
    (library / "other" / "db" / "dummy.template").write_text("record(ai, y) {}\n")
    return ["mylib:dev@1", "mylib:other@1"]


def _setup_req_in_support(epics: Path, library: Path) -> list[str]:
    # the sample tree's ADSimDetector/db holds dummy_settings.req
    (library / "other" / "db" / "dummy_settings.req").write_text("$(P)Y\n")
    return ["mylib:dev@1", "mylib:other@1"]


def _setup_req_in_autosave(epics: Path, library: Path) -> list[str]:
    (epics / "autosave").mkdir(exist_ok=True)
    (epics / "autosave" / "dev_settings.req").symlink_to("/nonexistent/x.req")
    return ["mylib:dev@1"]


def _setup_unroutable_file(epics: Path, library: Path) -> list[str]:
    (library / "other" / "ibek.manifest.yaml").unlink()  # default: every file
    return ["mylib:dev@1", "mylib:other@1"]


def _setup_no_version(epics: Path, library: Path) -> list[str]:
    return ["mylib:dev@1", "mylib:other"]


def _setup_no_library(epics: Path, library: Path) -> list[str]:
    return ["dev@1"]


def _setup_missing_pattern(epics: Path, library: Path) -> list[str]:
    return ["mylib:dev@1", "mylib:absent@1"]


def _setup_nested_database(epics: Path, library: Path) -> list[str]:
    (library / "other" / "other.ibek.support.yaml").write_text(
        support_yaml("other").replace(
            "    parameters: {}\n",
            "    parameters: {}\n    databases:\n      - file: db/other.template\n",
        )
    )
    return ["mylib:dev@1", "mylib:other@1"]


def _setup_nested_pvi(epics: Path, library: Path) -> list[str]:
    (library / "other" / "other.ibek.support.yaml").write_text(
        support_yaml("other").replace(
            "    parameters: {}\n",
            "    parameters: {}\n    pvi:\n      yaml_path: x/other.pvi.device.yaml\n",
        )
    )
    return ["mylib:dev@1", "mylib:other@1"]


def _setup_nested_backslash(epics: Path, library: Path) -> list[str]:
    (library / "other" / "other.ibek.support.yaml").write_text(
        support_yaml("other").replace(
            "    parameters: {}\n",
            "    parameters: {}\n    databases:\n      - file: db\\other.template\n",
        )
    )
    return ["mylib:dev@1", "mylib:other@1"]


def _setup_library_is_module_folder(epics: Path, library: Path) -> list[str]:
    # the sample tree's support/ holds the compiled module ADSimDetector
    return ["mylib:dev@1", "ADSimDetector:other@1"]


@pytest.mark.parametrize(
    "setup, message",
    [
        (_setup_module_in_image, "module 'dev' is already defined by"),
        (_setup_existing_file, "dev.proto already exists"),
        (_setup_shared_file, "mylib:other and mylib:dev both install"),
        (_setup_shared_module, "module 'dev' is already defined by pattern mylib:dev"),
        (_setup_same_name_twice_in_pattern, "is installed twice by this pattern"),
        (_setup_listed_twice, "listed more than once"),
        (_setup_selects_nothing, "nothing would be vendored"),
        (_setup_no_support_yaml, "mylib:other: selects no *.ibek.support.yaml"),
        (_setup_no_module, "declares no module"),
        (_setup_template_elsewhere, "dummy.template is also installed as"),
        (_setup_req_in_support, "dummy_settings.req is also installed as"),
        (_setup_req_in_autosave, "dev_settings.req is also installed as"),
        (_setup_unroutable_file, "no install location for README.md"),
        (_setup_no_version, "install needs library:pattern@version"),
        (_setup_no_library, "install needs library:pattern@version"),
        (_setup_missing_pattern, "pattern 'absent' not found"),
        (_setup_nested_database, "refers to 'db/other.template'"),
        (_setup_nested_pvi, "refers to 'x/other.pvi.device.yaml'"),
        (_setup_nested_backslash, "refers to 'db\\\\other.template'"),
        (_setup_library_is_module_folder, "a library must not share a support"),
    ],
)
def test_install_refusals_write_nothing(
    tmp_epics_root: Path, library: Path, setup, message: str, run
):
    refs = setup(tmp_epics_root, library)
    before = snapshot(tmp_epics_root)
    code, output = run("install", *refs, "--source", library)
    assert code == 1
    assert message in " ".join(output.split())
    assert snapshot(tmp_epics_root) == before


def test_same_database_name_from_two_libraries(
    tmp_epics_root: Path, tmp_path: Path, monkeypatch, run
):
    """Two libraries' templates land in different folders but share msi's path."""
    lib_a = make_pattern(tmp_path / "a", "dev", device_files("dev"))
    lib_b = make_pattern(tmp_path / "b", "other", device_files("other"))
    (lib_b / "other" / "db" / "dev.template").write_text("record(ai, z) {}\n")
    monkeypatch.setenv("IBEK_PATTERN_LIBRARIES", f"liba={lib_a},libb={lib_b}")
    before = snapshot(tmp_epics_root)
    code, output = run("install", "liba:dev@1", "libb:other@1")
    assert code == 1
    assert "have the same name" in output
    assert snapshot(tmp_epics_root) == before


def test_unknown_library(tmp_epics_root: Path, run):
    code, output = run("install", "nolib:dev@1")
    assert code == 1
    assert "unknown library 'nolib'" in output


def test_no_patterns(tmp_epics_root: Path, run):
    code, output = run("install")
    assert code == 1
    assert "no patterns to install" in output


# --------------------------------------------------------------------------- #
# the lock reaches the runtime image; generate2 reports shadowed modules
# --------------------------------------------------------------------------- #
def test_extract_runtime_assets_carries_lock(
    tmp_epics_root: Path, library: Path, tmp_path: Path, monkeypatch, run
):
    assert run("install", "mylib:dev@1.0.0", "--source", library)[0] == 0
    monkeypatch.chdir(tmp_path)
    assets = tmp_path / "assets"
    extract_assets(assets, tmp_epics_root, [], defaults=True)
    runtime_epics = assets / tmp_epics_root.relative_to("/")
    lock = runtime_epics / "ibek-defs" / IMAGE_LOCK_NAME
    assert lock.is_file()
    assert (runtime_epics / "support/mylib/db/dev.template").is_file()
    assert (runtime_epics / "support/configure/protocol/dev.proto").is_file()


def test_warn_shadowed_modules(tmp_path: Path, capsys):
    image = tmp_path / "ibek-defs" / "dev.ibek.support.yaml"
    other = tmp_path / "ibek-defs" / "other.ibek.support.yaml"
    instance = tmp_path / "config" / "dev.ibek.support.yaml"
    for path, module in ((image, "dev"), (other, "other"), (instance, "dev")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(support_yaml(module))
    broken = tmp_path / "config" / "broken.ibek.support.yaml"
    broken.write_text("module: [unclosed\n")

    warn_shadowed_modules([image, other], [instance, broken])
    err = capsys.readouterr().err
    assert "module 'dev' is defined by both the image" in err
    assert str(image) in err and str(instance) in err
    assert "'other'" not in err

    warn_shadowed_modules([other], [instance])
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "library_name, message",
    [
        ("../../outside", "must be a single folder name"),
        ("a/b", "must be a single folder name"),
        (".hidden", "must not start with '.'"),
        ("..", "must not start with '.'"),
        ("configure", "is reserved"),
    ],
)
def test_library_name_must_be_a_plain_folder(
    tmp_epics_root: Path, library: Path, run, library_name: str, message: str
):
    before = snapshot(tmp_epics_root.parent)
    code, output = run("install", f"{library_name}:dev@1.0", "--source", library)
    assert code == 1
    assert message in output
    assert snapshot(tmp_epics_root.parent) == before


def test_same_pattern_name_in_two_libraries(
    tmp_epics_root: Path, tmp_path: Path, run, monkeypatch
):
    """A pattern is identified by its library and its name together."""
    lib_a = make_pattern(tmp_path / "a", "dev", device_files("dev"))
    lib_b = make_pattern(tmp_path / "b", "dev", device_files("dev2"))
    monkeypatch.setenv("IBEK_PATTERN_LIBRARIES", f"liba={lib_a},libb={lib_b}")
    code, output = run("install", "liba:dev@1", "libb:dev@1")
    assert code == 0, output
    libraries = read_lock()["libraries"]
    assert libraries["liba"]["dev"]["modules"] == ["dev"]
    assert libraries["libb"]["dev"]["modules"] == ["dev2"]
    assert run("check", "--image")[0] == 0

    code, output = run("install", "libb:dev@1")
    assert code == 1
    assert "'libb:dev' is already installed" in output


def test_module_folder_after_install_without_database_files(
    tmp_epics_root: Path, tmp_path: Path, run
):
    """A library in the lock owns support/<library> only if it put files there."""
    files = device_files("dev")
    del files["db/dev.template"], files["db/dev_settings.req"]
    lib = make_pattern(tmp_path / "lib2", "dev", files)
    make_pattern(lib, "other", device_files("other"))
    assert run("install", "mylib:dev@1", "--source", lib)[0] == 0
    assert not (tmp_epics_root / "support" / "mylib").exists()

    # a compiled module of the library's name is built after that install
    (tmp_epics_root / "support" / "mylib" / "db").mkdir(parents=True)
    before = snapshot(tmp_epics_root)
    code, output = run("install", "mylib:other@1", "--source", lib)
    assert code == 1
    assert "a library must not share a support" in output
    assert snapshot(tmp_epics_root) == before
