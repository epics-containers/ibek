"""
Tests for the `ibek dev` commands.

Each test works on a generic IOC tree in a temporary folder. Every command that
ibek would run is recorded, and a stand-in does to the tree what ansible.sh
does to a container: it removes, clones and builds module folders.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import typer
from pytest_mock import MockerFixture
from ruamel.yaml import YAML
from typer.testing import CliRunner

from ibek.__main__ import cli
from ibek.dev_cmds import clones, drift
from ibek.dev_cmds.stamp import Stamp, StampError, compute, load
from ibek.globals import GLOBALS
from ibek.runtime_cmds.autosave import link_req_files

runner = CliRunner()

# the function that the tree fixture puts a stand-in for
RUN = drift.run

DOCKERFILE = """\
ARG REGISTRY=ghcr.io/epics-containers
ARG DEVELOPER=${REGISTRY}/epics-base-developer:7.0.11ec2
FROM  ${DEVELOPER} AS developer
ENV SOURCE_FOLDER=/epics/generic-source
COPY requirements.txt requirements.txt
RUN uv pip install --upgrade -r requirements.txt
WORKDIR ${SOURCE_FOLDER}/ibek-support
COPY ibek-support/_ansible _ansible
COPY ibek-support/asyn/ asyn
RUN ansible.sh asyn
COPY ibek-support/busy/ busy
RUN ansible.sh busy
COPY ibek-support-dls/motor/ motor
RUN ansible.sh motor
COPY ioc ${SOURCE_FOLDER}/ioc
RUN ansible.sh ioc
COPY Dockerfile requirements.txt ${SOURCE_FOLDER}/
RUN ibek dev stamp
FROM developer AS runtime_prep
"""


# the folders that the ansible runtime tasks link definition files into
LINKS = (
    ("ibek-defs", "*.ibek.support.yaml"),
    ("pvi-defs", "*.pvi.device.yaml"),
    ("autosave", "*.req"),
)


def write(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@dataclass
class Tree:
    epics: Path
    # every command ibek asked to run
    calls: list[list[str]] = field(default_factory=list)
    # the ansible.sh run with these arguments fails, e.g. "busy" or "ioc";
    # "schema" fails the schema generation
    fail_on: str = ""

    @property
    def source(self) -> Path:
        return self.epics / "generic-source"

    @property
    def binary(self) -> Path:
        return self.source / "ioc" / "bin" / "linux-x86_64" / "ioc"

    def make(self) -> None:
        """Build the IOC binary, as `make` in the IOC folder does."""
        write(self.binary)
        os.utime(self.binary, (time.time(), time.time()))

    def module(self, name: str) -> Path:
        return next(self.source.glob(f"ibek-support*/{name}"))

    def built(self, name: str) -> Path:
        """The folder a module is cloned to and built in."""
        return self.epics / "support" / name

    def ansible_sh(self, *words: str) -> None:
        """Do what ansible.sh does with these arguments."""
        # -v VERSION, the module, then arguments for ansible-playbook
        override = words[1] if words[0] == "-v" else None
        module, *rest = words[2:] if override else words
        args = tuple(rest)
        tags = args[args.index("--tags") + 1] if "--tags" in args else None
        folder = self.built(module)
        install = (
            self.module(module) / f"{module}.install.yml" if module != "ioc" else None
        )

        def clone() -> None:
            assert install is not None
            version = install.read_text().split("version: ")[1].split()[0]
            write(folder / "VERSION", override or version)

        if tags == "clone":
            # the clone tasks: with force_clone the folder is removed first
            if "force_clone=true" in args and folder.exists():
                shutil.rmtree(folder)
            if not folder.exists():
                clone()
        elif tags == "runtime":
            # the runtime tasks: link the definition files of each module
            for name in module.split(","):
                for target in self.module(name).iterdir():
                    for defs, pattern in LINKS:
                        link = self.epics / defs / target.name
                        if target.match(pattern) and not link.is_symlink():
                            link.symlink_to(target)
        elif tags is not None:
            # some other tasks, which neither clone nor build
            write(self.epics / "tools" / module, tags)
        else:
            # every task: an existing folder is not cloned again
            if module != "ioc" and not folder.exists():
                clone()
            if self.fail_on == module:
                raise typer.Exit(2)
            if module == "ioc":
                self.make()
            else:
                # the release tasks edit a tracked file, once
                release = folder / "configure" / "RELEASE"
                if release.exists() and "SUPPORT=" not in release.read_text():
                    release.write_text(release.read_text() + "SUPPORT=/epics/support\n")
                write(folder / "lib" / f"lib{module}.a", "built")

    def ansible(self) -> list[list[str]]:
        """The arguments of each ansible.sh call."""
        return [call[1:] for call in self.calls if call[0].endswith("/ansible.sh")]

    def dev(self, *args: object, code: int = 0) -> str:
        """Run `ibek dev ...` and return what it printed."""
        result = runner.invoke(cli, ["dev", *(str(arg) for arg in args)])
        assert result.exit_code == code, result.output
        # a command that fails says why: it never ends in a traceback
        assert not isinstance(result.exception, Exception), result.exception
        return result.output


@pytest.fixture
def tree(tmp_path: Path, mocker: MockerFixture) -> Tree:
    """A built generic IOC of three support modules, with its stamp."""
    made = Tree(tmp_path / "epics")
    source = made.source

    write(source / "Dockerfile", DOCKERFILE)
    write(source / "requirements.txt", "ibek>=5\n")
    ansible = source / "ibek-support" / "_ansible"
    write(ansible / "ansible.sh", "#!/bin/bash\n")
    write(ansible / "epics.ibek.support.yaml", "module: epics\n")
    write(ansible / "roles" / "support" / "tasks" / "clone.yml", "force_clone\n")

    for folder, name in (
        ("ibek-support", "asyn"),
        ("ibek-support", "busy"),
        ("ibek-support-dls", "motor"),
    ):
        module = source / folder / name
        write(module / f"{name}.install.yml", f"module: {name}\nversion: R1-0\n")
        write(module / f"{name}.ibek.support.yaml", f"module: {name}\n")
        write(made.built(name) / "VERSION", "R1-0")
        write(made.built(name) / "lib" / f"lib{name}.a", "built")
    write(made.module("motor") / "motor.pvi.device.yaml", "label: motor\n")
    write(made.module("busy") / "busy_settings.req", "$(P)busy\n")

    # the links that the ansible runtime tasks make at image build
    for folder, pattern in LINKS:
        (made.epics / folder).mkdir()
        for target in source.glob(f"ibek-support*/*/{pattern}"):
            (made.epics / folder / target.name).symlink_to(target)

    write(source / "ioc" / "start.sh", "#!/bin/bash\n")
    write(source / "ioc" / "Makefile", "TOP = .\n")
    write(source / "ioc" / "configure" / "RELEASE", "SUPPORT=/epics/support\n")
    write(source / "ioc" / "iocApp" / "src" / "Makefile", "PROD_IOC = ioc\n")
    write(source / "ioc" / "bin" / "linux-x86_64" / "ioc")
    (made.epics / "ioc").symlink_to(source / "ioc")

    def run(command: list[str], quiet: bool = False) -> None:
        made.calls.append(command)
        # only the definition links and the schema are done quietly
        level_1 = "runtime" in command or "generate-schema" in command
        assert quiet == level_1
        if made.fail_on == "schema" and "generate-schema" in command:
            raise typer.Exit(2)
        if "generate-schema" in command and drift.dangling():
            # the schema reads every link in the definition folder
            raise typer.Exit(1)
        if command[0].endswith("/ansible.sh"):
            made.ansible_sh(*command[1:])

    mocker.patch.object(GLOBALS, "_EPICS_ROOT", made.epics)
    mocker.patch.object(drift, "run", run)

    made.dev("stamp")
    return made


def test_stamp_file(tree: Tree):
    stamp = json.loads((tree.epics / "dev-stamp.json").read_text())

    assert stamp["schema"] == 1
    assert [module["name"] for module in stamp["modules"]] == ["asyn", "busy", "motor"]
    assert set(stamp["modules"][0]) == {
        "name",
        "defs",
        "build",
        "source",
        "options",
        "args",
    }
    assert set(stamp) == {
        "schema",
        "base",
        "requirements",
        "ansible",
        "modules",
        "pending",
        "rebuilt",
    }
    assert "matches" in tree.dev("status")


def test_stamp_needs_the_dockerfile(tree: Tree):
    (tree.source / "Dockerfile").unlink()

    assert "Dockerfile not found" in tree.dev("stamp", code=1)


def test_stamp_is_written_whole_or_not_at_all(tree: Tree):
    stamp = tree.epics / "dev-stamp.json"
    before = stamp.read_text()
    assert not stamp.with_name("dev-stamp.json.tmp").exists()

    # the stamp cannot be written: one line that names it, and the stamp intact
    stamp.with_name("dev-stamp.json.tmp").mkdir()
    write(tree.module("asyn") / "asyn.ibek.support.yaml", "module: asyn2\n")
    for args in (["stamp"], ["sync"]):
        lines = tree.dev(*args, code=1).splitlines()
        assert lines[-1].startswith(f"ibek dev: cannot write {stamp}: ")
        assert "Traceback" not in "".join(lines)
    assert stamp.read_text() == before


def test_stamp_ignores_what_git_does_not_track(tree: Tree, mocker: MockerFixture):
    """The image's tree after a build hashes the same as a host checkout."""
    before = compute()

    source = tree.source
    write(source / "ibek-support" / "asyn" / ".ansible" / "tmp" / "x")
    write(source / "ibek-support" / "asyn" / "asyn.build.log", "built")
    write(source / "ibek-support" / "_ansible" / "vars" / ".tmp.install.yml", "x: 1")
    write(source / "ibek-support" / "_ansible" / "__pycache__" / "a.pyc")
    # modes and line endings differ between checkouts
    install = tree.module("asyn") / "asyn.install.yml"
    install.chmod(0o755)
    install.write_bytes(install.read_bytes().replace(b"\n", b"\r\n"))
    requirements = source / "requirements.txt"
    requirements.write_bytes(requirements.read_bytes().replace(b"\n", b"\r\n"))

    assert compute() == before

    # and the same tree in another place
    shutil.copytree(tree.epics, tree.epics.parent / "copy", symlinks=True)
    mocker.patch.object(GLOBALS, "_EPICS_ROOT", tree.epics.parent / "copy")
    assert compute() == before


def test_stamp_reads_only_parts_of_the_dockerfile(tree: Tree):
    """A line that a build adds to the Dockerfile is not drift."""
    dockerfile = tree.source / "Dockerfile"
    text = dockerfile.read_text().replace(
        "WORKDIR", "ENV HTTP_PROXY=http://127.0.0.1:3128\nWORKDIR"
    )
    dockerfile.write_text(text + "\nRUN echo done\n")

    assert "matches" in tree.dev("status")


@pytest.mark.parametrize(
    "path, text, changed",
    [
        ("ibek-support/asyn/asyn.ibek.support.yaml", "x", {"defs"}),
        ("ibek-support/asyn/asyn.install.yml.orig", "x", {"build"}),
        ("ibek-support/asyn/.vscode/settings.json", "x", {"build"}),
        (
            "ibek-support/asyn/asyn.install.yml",
            "module: asyn\nversion: R1-0\ndbds: [asyn.dbd]\n",
            {"build"},
        ),
        (
            "ibek-support/asyn/asyn.install.yml",
            "module: asyn\nversion: R2\n",
            {"build", "source"},
        ),
        (
            "ibek-support/asyn/asyn.install.yml",
            "module: asyn\nversion: R1-0\norganization: https://example.com\n",
            {"build", "source"},
        ),
        ("ibek-support/_ansible/roles/support/tasks/build.yml", "x", {"ansible"}),
        ("requirements.txt", "x", {"requirements"}),
        ("ioc/iocApp/src/Makefile", "x", set()),
    ],
)
def test_stamp_sees_each_kind_of_change(tree: Tree, path: str, text: str, changed):
    before = compute()
    write(tree.source / path, text)
    after = compute()

    def parts(stamp):
        asyn = stamp.module("asyn")
        return {
            "defs": asyn.defs,
            "build": asyn.build,
            "source": asyn.source,
            "ansible": stamp.ansible,
            "requirements": stamp.requirements,
            "others": (stamp.base, stamp.modules[1:]),
        }

    differ = {key for key in parts(before) if parts(before)[key] != parts(after)[key]}
    assert differ == changed


def test_stamp_source_covers_the_patch_file(tree: Tree):
    asyn = tree.module("asyn")
    install = "module: asyn\nversion: R1-0\npatch_file:\n  path: asyn.patch\n"
    write(asyn / "asyn.install.yml", install)
    write(asyn / "asyn.patch", "one\n")
    before = compute().modules[0].source

    write(asyn / "asyn.patch", "two\n")
    assert compute().modules[0].source != before


def test_no_stamp(tree: Tree, tmp_path: Path):
    """An image built without a stamp: one line, exit 0, nothing run."""
    (tree.epics / "dev-stamp.json").unlink()
    write(tree.module("asyn") / "asyn.install.yml", "module: asyn\nversion: R2\n")

    for args in (
        ["status"],
        ["sync"],
        ["sync", "--build"],
    ):
        output = tree.dev(*args)
        assert output.count("\n") == 1
        assert "dev-stamp.json: this image was built without" in output

    instance = tmp_path / "bl01t-ea-test-01"
    (instance / "config").mkdir(parents=True)
    output = tree.dev("instance", instance)
    assert "built without `ibek dev stamp`" in output
    assert (tree.epics / "ioc" / "config").resolve() == instance / "config"

    assert tree.calls == []


@pytest.mark.parametrize(
    "text, message",
    [
        ('{"schema": 99}', "has schema 99, this ibek reads 1"),
        ("{", "cannot read"),
        ('{"schema": 1, "modules": 3}', "cannot read"),
        (b"\xff", "cannot read"),
    ],
)
def test_unreadable_stamp(tree: Tree, text: str | bytes, message: str):
    """One line: reported by status and sync, an error when asked to build."""
    stamp = tree.epics / "dev-stamp.json"
    stamp.write_bytes(text.encode() if isinstance(text, str) else text)
    write(tree.module("busy") / "busy.install.yml", "module: busy\nversion: R2\n")

    for args, code in ((["status"], 0), (["sync"], 0), (["sync", "--build"], 1)):
        lines = tree.dev(*args, code=code).splitlines()
        assert len(lines) == 1 and lines[0].startswith("ibek dev: ")
        assert message in lines[0] and str(stamp) in lines[0]

    assert tree.calls == []
    assert stamp.read_bytes() == (text.encode() if isinstance(text, str) else text)
    assert (tree.built("busy") / "VERSION").read_text() == "R1-0"


@pytest.mark.parametrize("submodule", ["ibek-support", "ibek-support-dls"])
def test_submodule_not_checked_out(tree: Tree, tmp_path: Path, submodule: str):
    """One line with the cause and the fix: no drift listed, nothing changed."""
    shutil.rmtree(tree.source / submodule)
    (tree.source / submodule).mkdir()
    instance = tmp_path / "bl01t-ea-test-01"
    (instance / "config").mkdir(parents=True)

    for args in (["status"], ["sync"], ["sync", "--build"], ["instance", instance]):
        # asked to build, there is nothing it can build: an error
        code = 1 if args == ["sync", "--build"] else 0
        lines = tree.dev(*args, code=code).splitlines()
        assert lines[-1].startswith(f"ibek dev: {tree.source / submodule} is not")
        assert "run `git submodule update --init` in the project" in lines[-1]
        assert len(lines) == (2 if args[0] == "instance" else 1)

    assert tree.calls == []
    # the links are left for when the submodule is there
    assert (tree.epics / "ibek-defs" / "motor.ibek.support.yaml").is_symlink()


def test_no_dockerfile(tree: Tree):
    (tree.source / "Dockerfile").unlink()

    for args, code in ((["status"], 0), (["sync"], 0), (["sync", "--build"], 1)):
        lines = tree.dev(*args, code=code).splitlines()
        assert lines == [
            f"ibek dev: {tree.source / 'Dockerfile'} not found: nothing to compare"
        ]
    assert tree.calls == []


def test_stamp_file_that_is_a_folder(tree: Tree):
    stamp = tree.epics / "dev-stamp.json"
    stamp.unlink()
    stamp.mkdir()

    for args, code in ((["status"], 0), (["sync"], 0), (["sync", "--build"], 1)):
        lines = tree.dev(*args, code=code).splitlines()
        assert len(lines) == 1 and lines[0].startswith(f"ibek dev: cannot read {stamp}")
    assert tree.calls == []


@pytest.mark.parametrize("name", ["Dockerfile", "requirements.txt"])
def test_dockerfile_or_requirements_that_is_not_text(tree: Tree, name: str):
    (tree.source / name).write_bytes(b"\xff")

    for args, code in ((["status"], 0), (["sync"], 0), (["sync", "--build"], 1)):
        lines = tree.dev(*args, code=code).splitlines()
        assert len(lines) == 1
        assert lines[0].startswith(f"ibek dev: cannot read {tree.source / name}")
    assert tree.calls == []


def test_unreadable_module_folder(tree: Tree, mocker: MockerFixture):
    """One line that names the folder."""
    asyn = tree.module("asyn")
    scandir = os.scandir

    def refuse(path):
        if Path(path) == asyn:
            raise PermissionError(13, "Permission denied", str(path))
        return scandir(path)

    mocker.patch("ibek.dev_cmds.stamp.os.scandir", refuse)

    for args, code in ((["status"], 0), (["sync"], 0), (["sync", "--build"], 1)):
        lines = tree.dev(*args, code=code).splitlines()
        assert lines == [f"ibek dev: cannot read {asyn}: Permission denied"]
    assert tree.calls == []


def test_module_named_twice_in_the_dockerfile(tree: Tree):
    """The module list is ordered and unique: the first naming counts."""
    dockerfile = tree.source / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace(
            "RUN ansible.sh motor", "RUN ansible.sh motor\nRUN ansible.sh busy"
        )
    )
    assert compute().names() == ["asyn", "busy", "motor"]
    assert "matches" in tree.dev("status")

    write(tree.module("busy") / "busy.install.yml.orig", "a stray file")
    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
    stamp = load()
    assert stamp is not None and stamp.names() == ["asyn", "busy", "motor"]


def test_dockerfile_module_with_no_ibek_support_folder(tree: Tree):
    """Nothing ibek can build: said as it is, with no command that cannot fix it."""
    dockerfile = tree.source / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace(
            "RUN ansible.sh busy", "RUN ansible.sh ghost\nRUN ansible.sh busy"
        )
    )

    for args in (["status"], ["sync"], ["sync", "--build"]):
        lines = tree.dev(*args).splitlines()
        assert len(lines) == 2
        assert lines[1].strip() == (
            f"ghost: the Dockerfile builds it, but {tree.source} does not have "
            "one ibek-support*/ghost folder"
        )
    assert tree.calls == []


def test_built_module_whose_ibek_support_folder_has_gone(tree: Tree):
    """The modules after it are not out of date: nothing is rebuilt."""
    shutil.rmtree(tree.module("busy"))
    line = (
        f"busy: the Dockerfile builds it, but {tree.source} does not have "
        "one ibek-support*/busy folder"
    )

    assert "rebuilds" not in tree.dev("status")
    reports = [tree.dev("sync", "--build").splitlines()[-2:] for _ in range(2)]

    assert reports[0] == reports[1]
    assert [text.strip() for text in reports[0]] == [
        f"ibek dev: this container differs from {tree.source}:",
        line,
    ]
    assert tree.ansible() == []
    assert (tree.built("motor") / "lib" / "libmotor.a").read_text() == "built"
    stamp = load()
    assert stamp is not None and stamp.names() == ["asyn", "busy", "motor"]
    assert stamp.pending == [] and stamp.rebuilt is None


def test_run_gives_the_exit_code_of_a_failed_command():
    RUN([sys.executable, "-c", "pass"])

    with pytest.raises(typer.Exit) as failed:
        RUN([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert failed.value.exit_code == 3

    with pytest.raises(typer.Exit) as failed:
        RUN(["/nowhere/no-such-command"])
    assert failed.value.exit_code == 1


def test_quiet_run_shows_its_output_only_when_it_fails(capfd):
    noisy = "import sys; print('PLAY'); print('+ set -x', file=sys.stderr); "

    RUN([sys.executable, "-c", noisy + "sys.exit(0)"], quiet=True)
    assert capfd.readouterr() == ("", "")

    with pytest.raises(typer.Exit) as failure:
        RUN([sys.executable, "-c", noisy + "sys.exit(3)"], quiet=True)
    assert failure.value.exit_code == 3
    out, err = capfd.readouterr()
    lines = err.splitlines()
    assert out == "" and sorted(lines[:2]) == ["+ set -x", "PLAY"]
    assert lines[2].startswith("ibek dev: failed: ") and len(lines) == 3


@pytest.mark.parametrize("failing", ["", "runtime", "generate-schema"])
def test_level_1_output(tree: Tree, mocker: MockerFixture, failing: str):
    """One line for each thing done; the commands' own output on a failure."""

    def run(command: list[str], quiet: bool = False) -> None:
        tree.calls.append(command)
        code = 3 if failing and failing in command else 0
        script = f"import sys; print('NOISE', {command[-1]!r}); sys.exit({code})"
        RUN([sys.executable, "-c", script], quiet=quiet)

    mocker.patch.object(drift, "run", run)
    write(tree.module("asyn") / "asyn.ibek.support.yaml", "module: asyn\n# more\n")
    write(tree.module("busy") / "busy_settings.req", "$(P)busy2\n")
    (tree.epics / "pvi-defs" / "gone.pvi.device.yaml").symlink_to("nowhere")
    schema = tree.epics / "ibek-defs" / "ioc.schema.json"

    lines = tree.dev("sync", code=3 if failing else 0).splitlines()

    done = [
        "ibek dev: linked the definition files of asyn, busy",
        "ibek dev: removed 1 dangling definition links",
        f"ibek dev: regenerated {schema}",
    ]
    if not failing:
        assert lines == [*done, f"ibek dev: this container matches {tree.source}"]
    elif failing == "runtime":
        assert lines[0] == "NOISE runtime" and len(lines) == 2
        assert lines[1].startswith("ibek dev: failed: ")
    else:
        assert lines[:3] == [*done[:2], f"NOISE {schema}"] and len(lines) == 4
        assert lines[3].startswith("ibek dev: failed: ")


def test_failing_ansible_run_stops_the_build(tree: Tree, mocker: MockerFixture):
    """With a real ansible.sh that fails: its exit code, and nothing after it."""
    log = tree.epics / "ansible.log"
    script = tree.source / "ibek-support" / "_ansible" / "ansible.sh"
    script.write_text(f'#!/bin/bash\necho "$@" >> {log}\nexit 7\n')
    script.chmod(0o755)
    tree.dev("stamp")
    mocker.patch.object(drift, "run", RUN)
    write(tree.module("busy") / "busy.install.yml.orig", "a stray file")

    output = tree.dev("sync", "--build", code=7)

    assert f"ibek dev: failed: {script} busy" in output
    assert log.read_text() == "busy\n"
    stamp = load()
    assert stamp is not None and stamp.pending == ["busy", "motor"]
    assert "busy: rebuild not finished" in tree.dev("status")


def test_level_1_definitions(tree: Tree):
    asyn = tree.module("asyn")
    write(asyn / "asyn.ibek.support.yaml", "module: asyn\nentity_models: []\n")
    (asyn / "asyn.ibek.support.yaml").rename(asyn / "asyn2.ibek.support.yaml")
    stale = tree.epics / "ibek-defs" / "asyn.ibek.support.yaml"
    assert stale.is_symlink()

    # status names the module and the command, and changes nothing
    output = tree.dev("status")
    assert "definitions changed: asyn; 1 dangling definition links" in output
    assert "fix: ibek dev sync\n" in output
    assert tree.calls == [] and stale.is_symlink()

    output = tree.dev("sync")
    schema = str(tree.epics / "ibek-defs" / "ioc.schema.json")
    assert tree.ansible() == [["asyn", "--tags", "runtime"]]
    assert tree.calls[-1][1:] == [
        "-m",
        "ibek",
        "ioc",
        "generate-schema",
        "--output",
        schema,
    ]
    assert len(tree.calls) == 2
    assert not stale.is_symlink()
    assert (tree.epics / "ibek-defs" / "asyn2.ibek.support.yaml").exists()
    assert "matches" in output

    # the stamp now describes the definitions in use
    tree.calls.clear()
    assert "matches" in tree.dev("sync")
    assert tree.calls == []


def test_dangling_links_alone(tree: Tree):
    for folder in ("ibek-defs", "pvi-defs", "autosave"):
        (tree.epics / folder / "gone.req").symlink_to(tree.epics / "nowhere")

    assert "3 dangling definition links" in tree.dev("status")
    tree.dev("sync")

    assert tree.ansible() == []
    assert len(tree.calls) == 1 and "generate-schema" in tree.calls[0]
    for folder in ("ibek-defs", "pvi-defs", "autosave"):
        assert not (tree.epics / folder / "gone.req").is_symlink()
    # links that resolve are kept
    assert (tree.epics / "ibek-defs" / "asyn.ibek.support.yaml").is_symlink()


def test_sync_leaves_regular_files_in_the_definition_folders(tree: Tree):
    """Files that `ibek pattern install` writes there are not links: kept."""
    files = {
        tree.epics / "ibek-defs" / "lakeshore.ibek.support.yaml": "module: lake\n",
        tree.epics / "ibek-defs" / "runtime-patterns.lock.yaml": "version: 1\n",
        tree.epics / "pvi-defs" / "lakeshore.pvi.device.yaml": "label: lake\n",
        tree.epics / "autosave" / "lakeshore_settings.req": "$(P)lake\n",
    }
    for path, text in files.items():
        write(path, text)
    assert "matches" in tree.dev("status")

    # both parts of the level 1 fix: links made again, dangling links removed
    write(tree.module("asyn") / "asyn.ibek.support.yaml", "module: asyn\n# more\n")
    (tree.epics / "pvi-defs" / "gone.pvi.device.yaml").symlink_to("nowhere")
    output = tree.dev("status")
    assert "definitions changed: asyn; 1 dangling definition links" in output

    assert "matches" in tree.dev("sync")
    assert tree.ansible() == [["asyn", "--tags", "runtime"]]
    assert not (tree.epics / "pvi-defs" / "gone.pvi.device.yaml").is_symlink()
    for path, text in files.items():
        assert not path.is_symlink() and path.read_text() == text


def test_level_2_is_reported_and_built_only_on_request(tree: Tree):
    """A new version in install.yml: the module is cloned again, with a warning."""
    write(tree.module("busy") / "busy.install.yml", "module: busy\nversion: R2\n")
    folder = tree.built("busy")
    edit = write(folder / "edit.c", "an edit to the source that is replaced")

    for command in ("status", "sync"):
        output = tree.dev(command)
        assert "busy: version, repository or patch changed" in output
        assert "rebuilds: busy, motor, then the IOC" in output
        assert f"clones busy again: {folder} and edits in it are removed" in output
        assert "fix: ibek dev sync --build" in output
        assert tree.calls == [] and edit.exists()

    output = tree.dev("sync", "--build")
    # the clone is a run of its own, for the changed module only
    assert tree.ansible() == [
        ["busy", "--tags", "clone", "-e", "force_clone=true"],
        ["busy"],
        ["motor"],
        ["ioc"],
    ]
    assert f"ibek dev: removing {folder} to clone busy again" in output
    assert (folder / "VERSION").read_text() == "R2" and not edit.exists()
    assert (tree.built("motor") / "VERSION").read_text() == "R1-0"
    assert "matches" in output

    tree.calls.clear()
    assert "matches" in tree.dev("sync", "--build")
    assert tree.calls == []


def test_level_2_failed_build_is_retried_on_the_same_clone(tree: Tree):
    """A fix made in the module folder after a failed build is kept."""
    write(tree.module("busy") / "busy.install.yml", "module: busy\nversion: R2\n")
    folder = tree.built("busy")

    tree.fail_on = "busy"
    tree.dev("sync", "--build", code=2)
    assert tree.ansible() == [
        ["busy", "--tags", "clone", "-e", "force_clone=true"],
        ["busy"],
    ]
    assert (folder / "VERSION").read_text() == "R2"
    assert not (folder / "lib").exists()
    # the clone is on record, the build is not
    stamp, live = load(), compute()
    assert stamp is not None and stamp.pending == ["busy", "motor"]
    assert stamp.modules[1].source == live.modules[1].source
    assert stamp.modules[1].build != live.modules[1].build

    fix = write(folder / "busyApp" / "src" / "fix.c", "what makes it build")
    tree.fail_on = ""
    for _ in range(2):
        tree.calls.clear()
        output = tree.dev("status")
        assert "busy: rebuild not finished" in output
        assert "clones" not in output and tree.calls == []

    output = tree.dev("sync", "--build")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
    assert fix.read_text() == "what makes it build"
    assert (folder / "lib" / "libbusy.a").exists()
    assert "removing" not in output and "matches" in output


def test_level_2_module_folder_that_is_a_link(tree: Tree):
    """A link is someone's own folder: never removed, built as it is."""
    folder = tree.built("busy")
    elsewhere = tree.epics / "elsewhere"
    shutil.move(folder, elsewhere)
    folder.symlink_to(elsewhere)
    edit = write(elsewhere / "edit.c", "work in progress")
    write(tree.module("busy") / "busy.install.yml", "module: busy\nversion: R2\n")

    output = tree.dev("status")
    assert "busy: version, repository or patch changed" in output
    assert f"busy: {folder} is a link, built as it is" in output
    assert "clones" not in output

    output = tree.dev("sync", "--build")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
    assert f"ibek dev: {folder} is a link: it is left alone" in output
    # built, and still reported: nothing says that this container matches
    assert "removing" not in output and "out of date" not in output
    assert "matches" not in output
    assert f"busy: {folder} is a link to {elsewhere} that is not declared" in output
    assert folder.resolve() == elsewhere and edit.read_text() == "work in progress"
    assert (elsewhere / "VERSION").read_text() == "R1-0"


@pytest.mark.parametrize(
    "path, text",
    [
        ("busy.install.yml.orig", "a stray file"),
        (".vscode/settings.json", "{}"),
        ("busy.install.yml", "module: busy\nversion: R1-0\ndbds: [busy.dbd]\n"),
    ],
)
def test_level_2_builds_in_place_when_the_source_is_the_same(
    tree: Tree, path: str, text: str
):
    """Only a change of what is cloned removes the module folder."""
    write(tree.module("busy") / path, text)
    edit = write(tree.built("busy") / "edit.c", "an edit to the source")

    output = tree.dev("status")
    assert "busy: build files changed" in output
    assert "clones busy again" not in output

    output = tree.dev("sync", "--build")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
    assert edit.exists() and (tree.built("busy") / "VERSION").read_text() == "R1-0"
    assert "removing" not in output and "matches" in output


def test_level_2_module_added(tree: Tree):
    """A module added to the Dockerfile is built, with those after it."""
    # ansible roles with no force_clone: a module with no folder needs none
    ansible = tree.source / "ibek-support" / "_ansible"
    write(ansible / "roles" / "support" / "tasks" / "clone.yml", "- name: Clone\n")
    tree.dev("stamp")

    write(
        tree.source / "ibek-support" / "calc" / "calc.install.yml",
        "module: calc\nversion: R3-7\n",
    )
    dockerfile = tree.source / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace(
            "RUN ansible.sh busy", "RUN ansible.sh calc\nRUN ansible.sh busy"
        )
    )

    output = tree.dev("sync")
    assert "calc: not built in this container" in output
    assert "rebuilds: calc, busy, motor, then the IOC" in output
    assert "clones" not in output
    assert tree.calls == []

    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [["calc"], ["busy"], ["motor"], ["ioc"]]
    assert (tree.built("calc") / "VERSION").read_text() == "R3-7"
    stamp = load()
    assert stamp is not None
    assert stamp.names() == ["asyn", "calc", "busy", "motor"]


def test_level_2_module_removed(tree: Tree):
    """A module the Dockerfile drops stays installed, and stays reported."""
    dockerfile = tree.source / "Dockerfile"
    dockerfile.write_text(dockerfile.read_text().replace("RUN ansible.sh busy\n", ""))
    installed = "busy: not in the Dockerfile, and installed until this container"

    output = tree.dev("status")
    assert "the Dockerfile's module list changed" in output
    assert "rebuilds: motor, then the IOC" in output
    assert installed in output

    output = tree.dev("sync", "--build")
    assert tree.ansible() == [["motor"], ["ioc"]]
    assert (tree.built("busy") / "lib" / "libbusy.a").exists()

    tree.calls.clear()
    for args in (["status"], ["sync"], ["sync", "--build"]):
        output = tree.dev(*args)
        assert installed in output
        assert "matches" not in output and "out of date" not in output
    assert tree.calls == []


def test_stamped_module_gone_from_the_tree_and_back(tree: Tree):
    """Its links are removed with it, and made again when it is back."""
    dockerfile = tree.source / "Dockerfile"
    text = dockerfile.read_text()
    busy = tree.module("busy")
    links = [
        tree.epics / "ibek-defs" / "busy.ibek.support.yaml",
        tree.epics / "autosave" / "busy_settings.req",
    ]

    # a checkout that has neither the Dockerfile line nor the folder
    dockerfile.write_text(text.replace("RUN ansible.sh busy\n", ""))
    shutil.move(busy, tree.epics / "busy")
    assert "2 dangling definition links" in tree.dev("status")
    tree.dev("sync")
    assert not any(link.is_symlink() for link in links)

    # the first checkout again
    dockerfile.write_text(text)
    shutil.move(tree.epics / "busy", busy)
    tree.calls.clear()
    output = tree.dev("status")
    assert "definitions changed: busy" in output and "out of date" not in output
    assert "matches" in tree.dev("sync")
    assert tree.ansible() == [["busy", "--tags", "runtime"]]
    assert all(link.is_symlink() and link.exists() for link in links)
    tree.calls.clear()
    assert "matches" in tree.dev("sync", "--build")
    assert tree.calls == []


def line(tree: Tree, text: str) -> None:
    """Give busy this line in the Dockerfile."""
    dockerfile = tree.source / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace("RUN ansible.sh busy\n", text + "\n")
    )


def test_dockerfile_line_with_tags_that_neither_clone_nor_build(tree: Tree):
    """The line is issued as it stands: no clone, no links."""
    tags = ["--tags", "system,pre_build_tasks"]
    line(tree, "RUN ansible.sh busy --tags system,pre_build_tasks")
    output = tree.dev("status")
    assert "busy: its Dockerfile line changed" in output
    assert "rebuilds: busy, motor, then the IOC" in output
    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [["busy", *tags], ["motor"], ["ioc"]]
    stamp = load()
    assert stamp is not None and stamp.modules[1].args == tags

    # another version: the line again, and the folder is not cloned again
    tree.calls.clear()
    write(tree.module("busy") / "busy.install.yml", "module: busy\nversion: R2\n")
    output = tree.dev("status")
    assert "busy: version, repository or patch changed" in output
    assert "clones" not in output
    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [["busy", *tags], ["motor"], ["ioc"]]
    assert (tree.built("busy") / "VERSION").read_text() == "R1-0"

    # its definition files are not linked by the line, so not by sync
    tree.calls.clear()
    write(tree.module("busy") / "busy_settings.req", "$(P)busy2\n")
    assert "matches" in tree.dev("sync")
    assert tree.calls == []


def test_dockerfile_line_with_a_version(tree: Tree):
    """-v decides the source: it goes with every command for the module."""
    line(tree, "RUN ansible.sh -v R2 busy")
    output = tree.dev("status")
    assert "busy: version, repository or patch changed" in output
    assert f"clones busy again: {tree.built('busy')}" in output
    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [
        ["-v", "R2", "busy", "--tags", "clone", "-e", "force_clone=true"],
        ["-v", "R2", "busy"],
        ["motor"],
        ["ioc"],
    ]
    assert (tree.built("busy") / "VERSION").read_text() == "R2"

    tree.calls.clear()
    write(tree.module("busy") / "busy_settings.req", "$(P)busy2\n")
    write(tree.module("asyn") / "asyn.ibek.support.yaml", "module: asyn\n# more\n")
    assert "matches" in tree.dev("sync")
    assert tree.ansible() == [
        ["asyn", "--tags", "runtime"],
        ["-v", "R2", "busy", "--tags", "runtime"],
    ]


def test_dockerfile_line_with_other_arguments(tree: Tree):
    """They go with every command for the module, after ibek's own tags."""
    extra = ["-e", "skip_clean=true"]
    line(tree, "RUN ansible.sh busy -e skip_clean=true")
    assert "busy: its Dockerfile line changed" in tree.dev("status")
    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [["busy", *extra], ["motor"], ["ioc"]]

    tree.calls.clear()
    write(tree.module("busy") / "busy.install.yml", "module: busy\nversion: R2\n")
    write(tree.module("busy") / "busy_settings.req", "$(P)busy2\n")
    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [
        ["busy", "--tags", "runtime", *extra],
        ["busy", "--tags", "clone", "-e", "force_clone=true", *extra],
        ["busy", *extra],
        ["motor"],
        ["ioc"],
    ]


@pytest.mark.parametrize(
    "text",
    [
        "RUN ansible.sh busy && echo done",
        "RUN ansible.sh busy \\",
        "RUN ansible.sh -x busy",
        "RUN ansible.sh busy 'unfinished",
    ],
)
def test_dockerfile_line_that_cannot_be_repeated(tree: Tree, text: str):
    """One line that names it, and nothing run."""
    line(tree, text)
    message = f"ibek dev: cannot repeat this line of {tree.source / 'Dockerfile'}: "

    for args, code in ((["status"], 0), (["sync"], 0), (["sync", "--build"], 1)):
        assert tree.dev(*args, code=code).splitlines() == [message + text]
    tree.dev("stamp", code=1)
    assert tree.calls == []


def test_level_2_ansible(tree: Tree):
    ansible = tree.source / "ibek-support" / "_ansible"
    write(ansible / "roles" / "support" / "tasks" / "build.yml", "- name: changed\n")

    output = tree.dev("sync")
    assert "ibek-support/_ansible changed: every module" in output
    assert "rebuilds: asyn, busy, motor, then the IOC" in output
    assert tree.calls == []

    assert "matches" in tree.dev("sync", "--build")
    # a change of recipe does not clone anything again
    assert tree.ansible() == [["asyn"], ["busy"], ["motor"], ["ioc"]]


def test_level_2_requirements(tree: Tree):
    """After an upgrade the old ibek that is running does nothing more."""
    write(tree.source / "requirements.txt", "ibek>=6\n")
    write(tree.module("busy") / "busy.install.yml", "module: busy\nversion: R2\n")

    output = tree.dev("sync")
    assert "requirements.txt changed" in output
    assert tree.calls == []

    output = tree.dev("sync", "--build")
    requirements = str(tree.source / "requirements.txt")
    assert tree.calls[0] == ["uv", "pip", "install", "--upgrade", "-r", requirements]
    assert "generate-schema" in tree.calls[1]
    assert len(tree.calls) == 2
    assert "Run `ibek dev sync --build` again for anything more." in output
    assert "requirements.txt changed" not in output
    assert "rebuilds: busy, motor, then the IOC" in output

    tree.calls.clear()
    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [
        ["busy", "--tags", "clone", "-e", "force_clone=true"],
        ["busy"],
        ["motor"],
        ["ioc"],
    ]


def test_level_2_requirements_when_the_schema_fails(tree: Tree):
    """The upgrade is not recorded, so the next run makes the schema."""
    write(tree.source / "requirements.txt", "ibek>=6\n")

    tree.fail_on = "schema"
    tree.dev("sync", "--build", code=2)
    assert "requirements.txt changed" in tree.dev("status")

    tree.fail_on = ""
    tree.calls.clear()
    assert "matches" in tree.dev("sync", "--build")
    assert tree.calls[0][0] == "uv"
    assert "generate-schema" in tree.calls[1] and len(tree.calls) == 2


def test_level_2_requirements_with_a_dangling_link(tree: Tree):
    """The links are put right before the schema, which reads them all."""
    write(tree.source / "requirements.txt", "ibek>=6\n")
    (tree.module("busy") / "busy.ibek.support.yaml").unlink()
    stale = tree.epics / "ibek-defs" / "busy.ibek.support.yaml"
    assert stale.is_symlink()

    output = tree.dev("sync", "--build")
    assert tree.calls[0][0] == "uv" and "generate-schema" in tree.calls[-1]
    assert tree.ansible() == [["busy", "--tags", "runtime"]]
    assert not stale.is_symlink()
    assert "Run `ibek dev sync --build` again for anything more." in output
    assert "matches" in output
    stamp = load()
    assert stamp is not None and stamp.requirements == compute().requirements

    tree.calls.clear()
    assert "matches" in tree.dev("sync", "--build")
    assert tree.calls == []


def test_level_2_build_resumes_after_a_failure(tree: Tree):
    write(tree.module("asyn") / "asyn.install.yml.orig", "a stray file")

    tree.fail_on = "busy"
    tree.dev("sync", "--build", code=2)
    assert tree.ansible() == [["asyn"], ["busy"]]

    tree.fail_on = ""
    tree.calls.clear()
    output = tree.dev("status")
    assert "busy: rebuild not finished" in output
    assert "rebuilds: busy, motor, then the IOC" in output
    assert "IOC: support modules were rebuilt after the IOC binary" in output

    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]


@pytest.mark.parametrize("text", ["- name: Clone\n", None])
def test_level_2_needs_force_clone_in_ibek_support(tree: Tree, text: str | None):
    clone = tree.source / "ibek-support/_ansible/roles/support/tasks/clone.yml"
    if text is None:
        clone.unlink()
    else:
        clone.write_text(text)
    tree.dev("stamp")
    write(tree.module("asyn") / "asyn.install.yml", "module: asyn\nversion: R3\n")

    assert "no force_clone" in tree.dev("sync", "--build", code=1)
    assert tree.calls == []
    assert (tree.built("asyn") / "VERSION").read_text() == "R1-0"


def test_level_3_base_image(tree: Tree):
    dockerfile = tree.source / "Dockerfile"
    dockerfile.write_text(dockerfile.read_text().replace("7.0.11ec2", "7.0.12ec1"))

    for args in (["status"], ["sync"], ["sync", "--build"]):
        output = tree.dev(*args)
        assert "base image changed" in output
        assert "pull a newer developer image or rebuild it locally" in output
    assert tree.calls == []


def test_ioc_reminder_is_cleared_by_make(tree: Tree):
    make = f"run `make` in {tree.epics / 'ioc'}"
    ioc = tree.source / "ioc"

    def age(path: Path, seconds: float) -> None:
        os.utime(path, (time.time() - seconds, time.time() - seconds))

    for path in ioc.glob("**/*"):
        age(path, 300)
    age(tree.binary, 120)
    assert "matches" in tree.dev("status")

    # what make does not build from: scripts, build products, the instance config
    age(ioc / "start.sh", 60)
    write(ioc / "iocApp" / "src" / "O.linux-x86_64" / "main.o")
    write(ioc / "configure" / "O.linux-x86_64" / "Makefile")
    write(ioc / "dbd" / "ioc.dbd")
    (ioc / "config").symlink_to(tree.epics)
    assert "matches" in tree.dev("status")

    # each kind of file that make builds the binary from
    for name in ("Makefile", "configure/RELEASE", "iocApp/src/Makefile"):
        age(tree.binary, 120)
        age(ioc / name, 60)
        output = tree.dev("sync")
        assert f"IOC: ioc source is newer than the IOC binary: {make}" in output
        # make builds a binary that is newer
        age(tree.binary, 30)
        assert "matches" in tree.dev("status")
    assert tree.calls == []

    # support modules rebuilt, and the IOC build after them failed
    write(tree.module("motor") / "motor.install.yml.orig", "a stray file")
    tree.fail_on = "ioc"
    tree.dev("sync", "--build", code=2)
    output = tree.dev("status")
    assert f"IOC: support modules were rebuilt after the IOC binary: {make}" in output
    tree.make()
    assert "matches" in tree.dev("status")

    # no binary at all
    shutil.rmtree(ioc / "bin")
    assert f"IOC: no IOC binary: {make}" in tree.dev("status")
    tree.fail_on = ""
    tree.calls.clear()
    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [["ioc"]]


def test_missing_module_folder(tree: Tree):
    motor = tree.module("motor")
    write(motor.parent / "README.md", "the submodule is checked out\n")
    shutil.move(motor, tree.epics / "motor")

    output = tree.dev("sync", "--build")
    assert "motor: the Dockerfile builds it, but" in output
    assert "have one ibek-support*/motor folder" in output
    assert "ibek dev sync --build" not in output
    assert tree.ansible() == []
    assert not (tree.epics / "pvi-defs" / "motor.pvi.device.yaml").is_symlink()

    # when the folder is back its definition files are linked again
    shutil.move(tree.epics / "motor", motor)
    tree.calls.clear()
    assert "definitions changed: motor" in tree.dev("status")
    tree.dev("sync")
    assert tree.ansible() == [["motor", "--tags", "runtime"]]


def test_instance_reports_drift(tree: Tree, tmp_path: Path):
    instance = tmp_path / "bl01t-ea-test-01"
    write(instance / "config" / "ioc.yaml", "ioc_name: test\n")
    write(tree.module("asyn") / "asyn.install.yml", "module: asyn\nversion: R2\n")

    output = tree.dev("instance", instance)

    assert (tree.epics / "ioc" / "config").resolve() == instance / "config"
    assert "asyn: version, repository or patch changed" in output
    assert "fix: ibek dev sync --build" in output
    assert tree.calls == []

    # a stamp that cannot be read: still no error
    (tree.epics / "dev-stamp.json").write_text("{")
    output = tree.dev("instance", instance)
    assert "cannot read" in output


WARNING = (
    "WARNING: this container was created from a different developer image "
    "than the one now on this machine. Use "
    '"Dev Containers: Rebuild Container" in VS Code to move to it.'
)


def image_ids(tree: Tree, created: str | bytes | None, now: str | bytes | None) -> None:
    """Write the image ID files; None leaves a file out."""
    for path, text in (
        (tree.epics / "dev-image-id", created),
        (tree.source / ".devcontainer" / "image-id", now),
    ):
        if text is not None:
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(text.encode() if isinstance(text, str) else text)


def all_commands(tree: Tree, tmp_path: Path) -> dict[str, str]:
    """The output of each command that reports, all of which exit 0."""
    instance = tmp_path / "bl01t-ea-test-01"
    (instance / "config").mkdir(parents=True, exist_ok=True)
    outputs = {
        "status": tree.dev("status"),
        "sync": tree.dev("sync"),
        "sync --build": tree.dev("sync", "--build"),
        "instance": tree.dev("instance", instance),
    }
    assert (tree.epics / "ioc" / "config").resolve() == instance / "config"
    return outputs


def test_stale_container_warning(tree: Tree, tmp_path: Path):
    """First in the report of each command, whose exit code stays 0."""
    image_ids(tree, "sha256:aaa\n", "sha256:bbb\n")
    stamp = (tree.epics / "dev-stamp.json").read_bytes()

    outputs = all_commands(tree, tmp_path)

    for command in ("status", "sync", "sync --build"):
        lines = outputs[command].splitlines()
        assert lines[0] == WARNING, command
        assert len(lines) == 2 and "matches" in lines[1], command
    # the instance command says what it links before it reports
    lines = outputs["instance"].splitlines()
    assert lines[0].startswith("Symlinking ")
    assert lines[1] == WARNING
    assert len(lines) == 3 and "matches" in lines[2]

    assert tree.calls == []
    assert (tree.epics / "dev-stamp.json").read_bytes() == stamp
    assert (tree.epics / "dev-image-id").read_text() == "sha256:aaa\n"
    assert (tree.source / ".devcontainer" / "image-id").read_text() == "sha256:bbb\n"


@pytest.mark.parametrize(
    "created, now",
    [
        ("sha256:aaa\n", "sha256:aaa\n"),
        ("sha256:aaa\n", "aaa"),
        ("aaa", "  sha256:aaa \r\n"),
        ("sha256:aaa\n", None),
        (None, "sha256:bbb\n"),
        (None, None),
        ("", "sha256:bbb\n"),
        ("sha256:aaa\n", "\n"),
        ("sha256:\n", "sha256:bbb\n"),
    ],
)
def test_no_stale_container_warning(
    tree: Tree, tmp_path: Path, created: str | None, now: str | None
):
    """The same image, or a file that is missing or empty: nothing is said."""
    image_ids(tree, created, now)

    for command, output in all_commands(tree, tmp_path).items():
        assert "WARNING" not in output, command
        assert "matches" in output, command


@pytest.mark.parametrize(
    "name", ["dev-image-id", "generic-source/.devcontainer/image-id"]
)
def test_no_stale_container_warning_for_an_unreadable_file(
    tree: Tree, tmp_path: Path, name: str
):
    """A file that cannot be read is no error and no warning."""
    image_ids(tree, "sha256:aaa\n", "sha256:bbb\n")
    path = tree.epics / name
    path.unlink()
    path.mkdir()

    for command, output in all_commands(tree, tmp_path).items():
        assert "WARNING" not in output, command
        assert "matches" in output, command


@pytest.mark.parametrize(
    "created, now",
    [(b"\xff\xfe", "sha256:bbb\n"), ("sha256:aaa\n", b"\xff\xfe")],
)
def test_no_stale_container_warning_for_an_id_that_is_not_text(
    tree: Tree, tmp_path: Path, created: str | bytes, now: str | bytes
):
    """A file that is not text is one that cannot be read."""
    image_ids(tree, created, now)

    for command, output in all_commands(tree, tmp_path).items():
        assert "WARNING" not in output, command
        assert "matches" in output, command


def test_stale_container_warning_with_no_stamp(tree: Tree, tmp_path: Path):
    """The warning does not need a stamp."""
    (tree.epics / "dev-stamp.json").unlink()
    image_ids(tree, "sha256:aaa\n", "sha256:bbb\n")

    outputs = all_commands(tree, tmp_path)

    for command, output in outputs.items():
        lines = output.splitlines()
        if command == "instance":
            assert lines.pop(0).startswith("Symlinking ")
        assert lines[0] == WARNING, command
        assert len(lines) == 2 and "built without `ibek dev stamp`" in lines[1]
    assert tree.calls == []
    assert not (tree.epics / "dev-stamp.json").exists()


def test_stale_container_warning_with_an_unreadable_stamp(tree: Tree):
    """The warning comes before the error, which keeps its exit code."""
    (tree.epics / "dev-stamp.json").write_text("{")
    image_ids(tree, "sha256:aaa\n", "sha256:bbb\n")

    for args, code in ((["status"], 0), (["sync"], 0), (["sync", "--build"], 1)):
        lines = tree.dev(*args, code=code).splitlines()
        assert lines[0] == WARNING
        assert len(lines) == 2 and "cannot read" in lines[1]


def test_stale_container_warning_with_other_drift(tree: Tree, tmp_path: Path):
    """The warning comes first, and the build is still done."""
    image_ids(tree, "sha256:aaa\n", "sha256:bbb\n")
    write(tree.module("busy") / "busy.install.yml", "module: busy\nversion: R2\n")
    instance = tmp_path / "bl01t-ea-test-01"
    (instance / "config").mkdir(parents=True)

    for args in (["status"], ["sync"]):
        lines = tree.dev(*args).splitlines()
        assert lines[0] == WARNING
        assert "differs from" in lines[1]
        assert "busy: version, repository or patch changed" in "\n".join(lines)
    lines = tree.dev("instance", instance).splitlines()
    assert lines[1] == WARNING and "differs from" in lines[2]
    assert tree.calls == []

    # a build prints a great deal: the warning is repeated after the report
    lines = tree.dev("sync", "--build").splitlines()
    assert lines[0] == WARNING and lines[-1] == WARNING
    assert lines.count(WARNING) == 2
    assert "matches" in lines[-2]
    assert tree.ansible() == [
        ["busy", "--tags", "clone", "-e", "force_clone=true"],
        ["busy"],
        ["motor"],
        ["ioc"],
    ]
    assert (tree.built("busy") / "VERSION").read_text() == "R2"

    # a build that fails keeps its exit code
    write(tree.module("motor") / "motor.install.yml", "module: motor\nversion: R2\n")
    tree.fail_on = "motor"
    output = tree.dev("sync", "--build", code=2)
    assert output.splitlines()[0] == WARNING


def test_stale_container_warning_is_repeated_only_after_a_build(tree: Tree):
    """Once when nothing is run or only links are made, twice after a build."""
    image_ids(tree, "sha256:aaa\n", "sha256:bbb\n")

    # nothing to do
    assert tree.dev("sync", "--build").count(WARNING) == 1
    assert tree.calls == []

    # definition files alone: linked without a build
    write(tree.module("motor") / "motor.ibek.support.yaml", "module: motor2\n")
    lines = tree.dev("sync", "--build").splitlines()
    assert lines[0] == WARNING and lines.count(WARNING) == 1
    assert tree.ansible() == [["motor", "--tags", "runtime"]]

    # the IOC alone
    tree.calls.clear()
    write(tree.source / "ioc" / "iocApp" / "src" / "Makefile", "PROD_IOC = ioc2\n")
    os.utime(tree.binary, (0, 0))
    assert tree.dev("sync").count(WARNING) == 1
    lines = tree.dev("sync", "--build").splitlines()
    assert lines[0] == WARNING and lines[-1] == WARNING
    assert lines.count(WARNING) == 2
    assert tree.ansible() == [["ioc"]]

    # the upgrade of the Python packages
    tree.calls.clear()
    write(tree.source / "requirements.txt", "ibek>=6\n")
    assert tree.dev("sync").count(WARNING) == 1
    lines = tree.dev("sync", "--build").splitlines()
    assert lines[0] == WARNING and lines[-1] == WARNING
    assert lines.count(WARNING) == 2
    assert "again for anything more." in "\n".join(lines)
    assert tree.calls[0][:3] == ["uv", "pip", "install"]

    # no warning, nothing repeated
    (tree.epics / "dev-image-id").unlink()
    write(tree.module("busy") / "busy.install.yml", "module: busy\nversion: R2\n")
    assert "WARNING" not in tree.dev("sync", "--build")


# ---------------------------------------------------------------------------
# ibek dev support


def git(folder: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(folder), *args], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@dataclass
class Work:
    """Repositories for the three support modules, and a /workspaces folder."""

    tree: Tree
    upstream: Path
    workspaces: Path
    # the stamp of the image
    stamp: str = ""

    def clone(self, name: str) -> Path:
        return self.workspaces / name

    def declarations(self) -> dict[str, str]:
        file = self.tree.source / ".ibek-dev.yaml"
        if not file.exists():
            return {}
        return YAML(typ="safe").load(file.read_text())["support"]

    def own_clone(self, name: str, url: str | None = None) -> Path:
        """A clone that its developer made, on a branch of their own."""
        clone = self.clone(name)
        git(self.upstream, "clone", str(self.upstream / name), str(clone))
        git(clone, "checkout", "-b", "work")
        if url is not None:
            git(clone, "remote", "set-url", "origin", url)
        return clone

    def recreate(self) -> None:
        """A container made again from the image: only the host folders stay."""
        for name in ("asyn", "busy", "motor"):
            folder = self.tree.built(name)
            if folder.is_symlink():
                folder.unlink()
            elif folder.exists():
                shutil.rmtree(folder)
            write(folder / "VERSION", "R1-0")
            write(folder / "lib" / f"lib{name}.a", "built")
        (self.tree.epics / "dev-stamp.json").write_text(self.stamp)


@pytest.fixture
def work(tree: Tree, tmp_path: Path, mocker: MockerFixture, monkeypatch) -> Work:
    for key, value in (
        ("GIT_CONFIG_GLOBAL", "/dev/null"),
        ("GIT_CONFIG_SYSTEM", "/dev/null"),
        ("GIT_AUTHOR_NAME", "A Developer"),
        ("GIT_AUTHOR_EMAIL", "dev@example.com"),
        ("GIT_COMMITTER_NAME", "A Developer"),
        ("GIT_COMMITTER_EMAIL", "dev@example.com"),
    ):
        monkeypatch.setenv(key, value)
    made = Work(tree, tmp_path / "upstream", tmp_path / "workspaces")
    made.workspaces.mkdir()
    for name in ("asyn", "busy", "motor"):
        repo = made.upstream / name
        write(repo / "configure" / "RELEASE", "EPICS_BASE=/epics/epics-base\n")
        write(repo / "src" / f"{name}.c", "int released;\n")
        git(repo, "init", "--quiet", "--initial-branch", "main")
        git(repo, "add", ".")
        git(repo, "commit", "--quiet", "-m", "the release")
        git(repo, "tag", "R1-0")
        write(repo / "src" / f"{name}.c", "int later;\n")
        git(repo, "commit", "--quiet", "-am", "work after the release")
        write(
            tree.module(name) / f"{name}.install.yml",
            f"module: {name}\nversion: R1-0\ngit_repo: {repo}\n",
        )
    mocker.patch.object(clones, "WORKSPACES", made.workspaces)
    tree.dev("stamp")
    made.stamp = (tree.epics / "dev-stamp.json").read_text()
    return made


def test_support_clones_links_and_builds(work: Work):
    tree, clone, folder = work.tree, work.clone("busy"), work.tree.built("busy")

    output = tree.dev("support", "busy")

    # a whole clone, at the version of install.yml
    assert git(clone, "rev-parse", "HEAD") == git(clone, "rev-parse", "R1-0^{commit}")
    assert git(clone, "rev-parse", "--is-shallow-repository") == "false"
    assert git(clone, "log", "--oneline", "--all").count("\n") == 1
    # in place of the module that the image built: no copy of that is kept
    assert folder.is_symlink() and folder.resolve() == clone
    assert not (clone / "VERSION").exists()
    assert sorted(p.name for p in (tree.epics / "support").iterdir()) == [
        "asyn",
        "busy",
        "motor",
    ]
    assert not (tree.epics / "support-prebuilt").exists()
    # built, with what follows it in the Dockerfile and the IOC
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
    assert (clone / "lib" / "libbusy.a").exists()
    assert work.declarations() == {"busy": str(clone)}
    assert f"ibek dev: removing {folder} and linking it to {clone}" in output
    assert "matches" in output
    assert f"ibek dev: busy is linked to its clone {clone}" in output

    # what the build made is out of git's sight; the tracked file that it
    # edited is not, and is named
    assert git(clone, "status", "--porcelain") == "M configure/RELEASE"
    assert "/lib/" in (clone / ".git" / "info" / "exclude").read_text()
    notice = output[output.index("the build edited these tracked files") :]
    assert "do not commit those edits" in notice
    assert notice.splitlines()[1].strip() == "configure/RELEASE"

    for command in ("status", "sync", "sync --build"):
        tree.calls.clear()
        output = tree.dev(*command.split())
        assert "matches" in output and "busy is linked to its clone" in output
        assert tree.calls == []

    # again: a build of the clone as it now is
    edit = write(clone / "src" / "new.c", "int added;\n")
    output = tree.dev("support", "busy")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
    assert "removing" not in output and "matches" in output
    assert "the build edited" not in output and edit.exists()
    # the developer's own file is theirs to see
    assert "?? src/new.c" in git(clone, "status", "--porcelain")


def test_support_never_clones_a_declared_module_again(work: Work):
    tree, clone = work.tree, work.clone("busy")
    tree.dev("support", "busy")
    edit = write(clone / "src" / "busy.c", "int edited;\n")
    install = tree.module("busy") / "busy.install.yml"
    install.write_text(install.read_text().replace("R1-0", "main"))

    output = tree.dev("status")
    assert "busy: version, repository or patch changed" in output
    assert "is a link, built as it is" in output and "clones busy" not in output

    for recreate in (False, True):
        if recreate:
            work.recreate()
            assert "clones busy" not in tree.dev("status")
        tree.calls.clear()
        assert "matches" in tree.dev("sync", "--build")
        assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
        assert edit.read_text() == "int edited;\n"
        assert tree.built("busy").resolve() == clone


def test_support_of_several_modules(work: Work):
    tree = work.tree

    output = tree.dev("support", "motor", "asyn")
    # one build, from the first of them in the Dockerfile
    assert tree.ansible() == [["asyn"], ["busy"], ["motor"], ["ioc"]]
    assert work.declarations() == {
        "motor": str(work.clone("motor")),
        "asyn": str(work.clone("asyn")),
    }
    assert "matches" in output
    assert not tree.built("busy").is_symlink()

    tree.calls.clear()
    tree.dev("support", "busy")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
    assert set(work.declarations()) == {"asyn", "busy", "motor"}
    for name in ("asyn", "busy", "motor"):
        assert tree.built(name).resolve() == work.clone(name)

    # in another container: reported, then all linked and built by one command
    work.recreate()
    tree.calls.clear()
    output = tree.dev("sync")
    assert "rebuilds: asyn, busy, motor, then the IOC" in output
    assert tree.calls == []
    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [["asyn"], ["busy"], ["motor"], ["ioc"]]
    for name in ("asyn", "busy", "motor"):
        assert tree.built(name).resolve() == work.clone(name)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/epics-modules/busy",
        "https://github.com/epics-modules/busy.git",
        "https://GitHub.com/epics-modules/busy/",
        "https://user@github.com/epics-modules/busy.git",
        "git@github.com:epics-modules/busy.git",
        "ssh://git@github.com/epics-modules/busy",
        "ssh://git@github.com:22/epics-modules/busy.git",
    ],
)
def test_same_repo(url: str):
    assert clones.same_repo(url, "https://github.com/epics-modules/busy")
    assert not clones.same_repo(url, "https://github.com/epics-modules/asyn")
    assert not clones.same_repo(url, "https://github.com/someone/busy")
    assert not clones.same_repo(url, "https://gitlab.com/epics-modules/busy")


def test_support_uses_a_clone_that_is_there(work: Work):
    """Its branch, its edits and its untracked files are its developer's."""
    tree = work.tree
    clone = work.own_clone("busy")
    write(clone / "src" / "busy.c", "int edited;\n")
    write(clone / "notes.txt", "mine\n")

    output = tree.dev("support", "busy")

    line = f"ibek dev: {clone} is at work, not at the R1-0 of busy.install.yml"
    assert output.count(line) == 1
    assert git(clone, "rev-parse", "--abbrev-ref", "HEAD") == "work"
    assert (clone / "src" / "busy.c").read_text() == "int edited;\n"
    assert tree.built("busy").resolve() == clone
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
    # the developer's edit shows, and is not said to be the build's
    status = [line.strip() for line in git(clone, "status", "--porcelain").splitlines()]
    assert sorted(status) == ["?? notes.txt", "M configure/RELEASE", "M src/busy.c"]
    notice = output[output.index("the build edited these tracked files") :]
    assert "configure/RELEASE" in notice and "src/busy.c" not in notice

    # at the version of install.yml: nothing to say
    git(clone, "stash", "--quiet")
    git(clone, "checkout", "--quiet", "R1-0")
    assert "is at" not in tree.dev("support", "busy")


def test_support_takes_a_remote_that_is_not_origin(work: Work):
    """A clone of a fork, with the module's repository as another remote."""
    clone = work.own_clone("busy", "https://example.com/fork/busy")
    git(clone, "remote", "add", "upstream", f"{work.upstream / 'busy'}/")

    assert "matches" in work.tree.dev("support", "busy")


@pytest.mark.parametrize("kind", ["other repo", "no remote", "folder", "file", "link"])
def test_support_refuses_what_is_not_a_clone_of_the_module(work: Work, kind: str):
    tree, clone, folder = work.tree, work.clone("busy"), work.tree.built("busy")
    if kind == "other repo":
        work.own_clone("busy", "https://example.com/other/thing.git")
    elif kind == "no remote":
        git(work.own_clone("busy"), "remote", "remove", "origin")
    elif kind == "folder":
        # a folder of some other repository is not a clone either
        git(work.workspaces, "init", "--quiet")
        write(clone / "README", "not a clone\n")
    elif kind == "file":
        write(clone, "not a folder\n")
    else:
        clone.symlink_to(work.workspaces / "nowhere")

    output = tree.dev("support", "busy", code=1)

    if kind in ("other repo", "no remote"):
        assert f"{clone} is not a clone of {work.upstream / 'busy'}" in output
        remotes = "https://example.com/other/thing.git" if "other" in kind else "none"
        assert f"its remotes are {remotes}" in output
    else:
        assert f"{clone} exists and is not a git clone that can be used" in output
    # nothing was changed
    assert folder.is_dir() and not folder.is_symlink()
    assert (folder / "VERSION").read_text() == "R1-0"
    assert work.declarations() == {} and tree.calls == []
    assert "matches" in tree.dev("status")


def test_support_refuses_before_changing_anything(work: Work):
    """With several modules, one that cannot be used stops them all."""
    tree = work.tree
    work.own_clone("motor", "https://example.com/other/thing.git")

    tree.dev("support", "busy", "motor", code=1)

    assert not tree.built("busy").is_symlink()
    assert work.declarations() == {} and tree.calls == []
    assert "matches" in tree.dev("status")


@pytest.mark.parametrize("name", ["nothing", "ioc", "/workspaces/busy"])
def test_support_of_what_the_dockerfile_does_not_build(work: Work, name: str):
    output = work.tree.dev("support", name, code=1)
    assert f"{name} is not a support module that the Dockerfile clones" in output
    assert "those are asyn, busy, motor" in output
    assert work.declarations() == {}


def test_support_with_no_stamp(work: Work):
    (work.tree.epics / "dev-stamp.json").unlink()
    output = work.tree.dev("support", "busy", code=1)
    assert "nothing to compare" in output
    assert not work.clone("busy").exists() and work.declarations() == {}


def test_support_when_the_clone_fails(work: Work):
    tree = work.tree
    install = tree.module("busy") / "busy.install.yml"
    install.write_text(f"module: busy\nversion: R1-0\ngit_repo: {work.upstream}/no\n")
    tree.dev("stamp")

    output = tree.dev("support", "busy", code=1)
    assert "ibek dev: failed: git" in output
    assert not tree.built("busy").is_symlink() and work.declarations() == {}

    # a version that the repository does not have: the clone is left
    install.write_text(
        f"module: busy\nversion: R9\ngit_repo: {work.upstream / 'busy'}\n"
    )
    tree.dev("stamp")
    output = tree.dev("support", "busy", code=1)
    assert f"{work.clone('busy')} is left as it is" in output
    assert not tree.built("busy").is_symlink() and work.declarations() == {}
    assert tree.calls == []


def test_support_names_a_patch_that_it_does_not_apply(work: Work):
    tree = work.tree
    install = tree.module("busy") / "busy.install.yml"
    install.write_text(install.read_text() + "patch_file:\n  path: fix.patch\n")
    patch = write(tree.module("busy") / "fix.patch", "a patch\n")
    tree.dev("stamp")

    output = tree.dev("support", "busy")
    assert f"busy.install.yml applies {patch} to the clone that it makes" in output


def test_support_with_a_version_on_the_dockerfile_line(work: Work):
    tree = work.tree
    line(tree, "RUN ansible.sh -v main busy")
    tree.dev("stamp")

    tree.dev("support", "busy")
    clone = work.clone("busy")
    assert git(clone, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert tree.ansible() == [["-v", "main", "busy"], ["motor"], ["ioc"]]


def test_support_leaves_other_drift_reported(work: Work):
    """Only the module and what follows it are built and put on record."""
    tree = work.tree
    write(tree.source / "ibek-support" / "_ansible" / "roles" / "new.yml", "new\n")
    write(tree.module("asyn") / "asyn.install.yml.orig", "a stray file")

    output = tree.dev("support", "motor")

    assert tree.ansible() == [["motor"], ["ioc"]]
    assert "ibek-support/_ansible changed: every module" in output
    assert "asyn: build files changed" in output
    assert "rebuilds: asyn, busy, motor, then the IOC" in output
    assert "matches" in tree.dev("sync", "--build")
    assert tree.built("motor").resolve() == work.clone("motor")


def test_release(work: Work):
    tree, clone, folder = work.tree, work.clone("busy"), work.tree.built("busy")
    tree.dev("support", "asyn", "busy")
    edit = write(clone / "src" / "busy.c", "int edited;\n")
    tree.calls.clear()

    output = tree.dev("support", "--release", "busy")

    # the link and the declaration go: the clone stays, nothing is built
    assert f"ibek dev: removed the link {folder}: its clone is left alone" in output
    assert not folder.is_symlink() and not folder.exists()
    assert edit.read_text() == "int edited;\n"
    assert work.declarations() == {"asyn": str(work.clone("asyn"))}
    assert tree.calls == []
    for said in (output, tree.dev("status"), tree.dev("sync")):
        assert "matches" not in said
        assert f"busy: {folder} is missing" in said
        assert "rebuilds: busy, motor, then the IOC" in said
        assert "fix: ibek dev sync --build" in said
    assert tree.calls == []

    # the build that the report names clones the version of install.yml
    output = tree.dev("sync", "--build")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
    assert folder.is_dir() and not folder.is_symlink()
    assert (folder / "VERSION").read_text() == "R1-0"
    assert "matches" in output and "busy is linked" not in output
    assert tree.built("asyn").resolve() == work.clone("asyn")

    # the last declaration takes the file with it
    tree.dev("support", "--release", "asyn")
    assert not (tree.source / ".ibek-dev.yaml").exists()

    # nothing to release
    output = tree.dev("support", "--release", "busy", "nothing", code=1)
    assert "busy, nothing: not declared for development, and no link" in output
    assert folder.is_dir()


def test_release_in_a_container_that_never_linked_the_module(work: Work):
    tree = work.tree
    tree.dev("support", "busy")
    work.recreate()

    output = tree.dev("support", "--release", "busy")
    assert "ibek dev: busy is no longer declared for development" in output
    # the module of the image is the one in use
    assert "matches" in output and work.declarations() == {}
    assert (tree.built("busy") / "VERSION").read_text() == "R1-0"


def test_release_of_a_link_that_is_not_declared(work: Work):
    tree, folder = work.tree, work.tree.built("busy")
    elsewhere = tree.epics / "elsewhere"
    shutil.move(folder, elsewhere)
    folder.symlink_to(elsewhere)

    for command in ("status", "sync", "sync --build"):
        output = tree.dev(*command.split())
        assert "matches" not in output
        assert f"busy: {folder} is a link to {elsewhere} that is not declared" in output
    assert tree.calls == []

    tree.dev("support", "busy", code=1)
    assert folder.resolve() == elsewhere and work.declarations() == {}

    output = tree.dev("support", "--release", "busy")
    assert f"busy: {folder} is missing" in output
    assert elsewhere.is_dir()
    assert "matches" in tree.dev("sync", "--build")


def test_recreated_container_reports_and_builds_only_on_request(work: Work):
    tree, clone, folder = work.tree, work.clone("busy"), work.tree.built("busy")
    tree.dev("support", "busy")
    work.recreate()

    for command in ("status", "sync"):
        tree.calls.clear()
        output = tree.dev(command)
        assert "matches" not in output
        assert (
            f"busy: declared for development in {clone}, but {folder} is not "
            "a link to it"
        ) in output
        assert f"links {folder} to {clone}: the busy that is there is removed" in output
        assert "rebuilds: busy, motor, then the IOC" in output
        assert "fix: ibek dev sync --build" in output
        # nothing is compiled or linked unasked
        assert tree.calls == [] and folder.is_dir() and not folder.is_symlink()

    output = tree.dev("sync", "--build")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
    assert f"ibek dev: removing {folder} and linking it to {clone}" in output
    assert folder.resolve() == clone and "matches" in output


def test_interrupted_support_is_never_a_match(work: Work, mocker: MockerFixture):
    tree, clone, folder = work.tree, work.clone("busy"), work.tree.built("busy")

    # the stamp cannot be written: stopped before the module is replaced
    save = mocker.patch.object(Stamp, "save", side_effect=StampError("no stamp"))
    assert "no stamp" in tree.dev("support", "busy", code=1)
    assert folder.is_dir() and not folder.is_symlink() and tree.calls == []
    mocker.stop(save)
    output = tree.dev("status")
    assert "matches" not in output and "busy: declared for development" in output

    # the build fails: the link is to a clone that is not built
    tree.fail_on = "busy"
    tree.dev("support", "busy", code=2)
    assert folder.resolve() == clone and not (clone / "lib").exists()
    for command in ("status", "sync"):
        output = tree.dev(command)
        assert "matches" not in output and "busy: rebuild not finished" in output

    # the link cannot be made: the pre-built module has gone
    work.recreate()
    tree.fail_on = ""
    link = mocker.patch.object(Path, "symlink_to", side_effect=OSError("no link"))
    output = tree.dev("sync", "--build", code=1)
    assert f"cannot link {folder} to {clone}: no link" in output
    mocker.stop(link)
    assert not folder.exists()
    output = tree.dev("status")
    assert "matches" not in output and "busy: declared for development" in output

    tree.calls.clear()
    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
    assert folder.resolve() == clone


def test_declaration_that_cannot_be_written(work: Work):
    tree = work.tree
    (tree.source / ".ibek-dev.yaml").mkdir()

    output = tree.dev("support", "busy", code=1)
    assert f"cannot read {tree.source / '.ibek-dev.yaml'}" in output
    assert not tree.built("busy").is_symlink() and tree.calls == []


@pytest.mark.parametrize(
    "text", ["support: [busy]\n", "- busy\n", "support:\n  busy:\n", "{", b"\xff"]
)
def test_declarations_that_cannot_be_read(work: Work, text: str | bytes):
    tree = work.tree
    tree.dev("support", "busy")
    file = tree.source / ".ibek-dev.yaml"
    file.write_bytes(text.encode() if isinstance(text, str) else text)

    for command in ("status", "sync", "sync --build"):
        output = tree.dev(*command.split())
        assert f"cannot read {file}: {file} holds `support:`" in output
        assert "matches" not in output
    for args in (["busy"], ["--release", "busy"]):
        assert f"cannot read {file}" in tree.dev("support", *args, code=1)
    assert tree.built("busy").is_symlink()


@pytest.mark.parametrize("text", ["module: [busy\n", "- a list\n", b"\xff", None])
def test_declared_module_with_an_unreadable_install_yml(
    work: Work, text: str | bytes | None
):
    tree = work.tree
    install = tree.module("busy") / "busy.install.yml"
    tree.dev("support", "motor", "busy")
    tree.calls.clear()
    if text is None:
        install.unlink()
    else:
        install.write_bytes(text.encode() if isinstance(text, str) else text)

    for command in ("status", "sync"):
        output = tree.dev(command)
        assert "matches" not in output
        assert "busy: declared for development, but its install.yml cannot" in output
    assert tree.calls == []
    output = tree.dev("support", "busy", code=1)
    assert "busy.install.yml" in output and tree.calls == []

    # released all the same, from the folder that a module has by default
    tree.dev("support", "--release", "busy")
    assert not tree.built("busy").is_symlink()
    assert work.declarations() == {"motor": str(work.clone("motor"))}


def test_declared_module_whose_clone_has_gone(work: Work):
    tree, clone, folder = work.tree, work.clone("busy"), work.tree.built("busy")
    tree.dev("support", "busy")
    shutil.rmtree(clone)
    tree.calls.clear()

    for command in ("status", "sync", "sync --build"):
        output = tree.dev(*command.split())
        assert "matches" not in output
        assert f"busy: declared for development, but its clone {clone} is" in output
    assert tree.calls == []

    # something else to build: the link to nothing stops it, in one line
    write(tree.module("asyn") / "asyn.install.yml.orig", "a stray file")
    output = tree.dev("sync", "--build", code=1)
    assert f"busy cannot be built: {folder} is a link to {clone}, which is" in output
    assert tree.calls == []

    # cloned again by the command that made it
    output = tree.dev("support", "busy")
    assert folder.resolve() == clone and (clone / "lib" / "libbusy.a").exists()
    assert "matches" in tree.dev("sync", "--build")


def test_declared_module_that_the_dockerfile_dropped(work: Work):
    tree = work.tree
    tree.dev("support", "motor")
    dockerfile = tree.source / "Dockerfile"
    dockerfile.write_text(dockerfile.read_text().replace("RUN ansible.sh motor\n", ""))

    output = tree.dev("status")
    assert "motor: declared for development, and not a module of the" in output
    tree.dev("support", "--release", "motor")
    assert work.declarations() == {}


def test_module_folder_that_has_gone(tree: Tree):
    """Not a match: built again from a clone that ansible makes."""
    shutil.rmtree(tree.built("busy"))

    for command in ("status", "sync"):
        output = tree.dev(command)
        assert "matches" not in output
        assert f"busy: {tree.built('busy')} is missing" in output
    assert tree.calls == []

    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]


def test_build_products_in_a_clone_with_a_git_folder_elsewhere(work: Work):
    """A clone that is a git worktree has no .git folder of its own."""
    tree = work.tree
    main = work.own_clone("busy")
    shutil.move(main, work.workspaces / "busy-main")
    main = work.workspaces / "busy-main"
    clone = work.clone("busy")
    git(main, "worktree", "add", "--quiet", str(clone), "R1-0")

    tree.dev("support", "busy")

    assert git(clone, "status", "--porcelain") == "M configure/RELEASE"
    assert (clone / "lib" / "libbusy.a").exists()


def test_autosave_links_through_a_module_link(work: Work):
    """Request files of a linked clone are found; a looping link is not followed."""
    tree, clone = work.tree, work.clone("busy")
    tree.dev("support", "busy")
    write(clone / "db" / "busy_settings.req", "$(P)busy\n")
    write(clone / "db" / "busyRecord_settings.req", "$(P)record\n")
    (clone / "db" / "loop").symlink_to(clone)
    (clone / "self").symlink_to(".")
    write(tree.built("asyn") / "db" / "asyn_settings.req", "$(P)asyn\n")
    write(tree.epics / "support" / "top.req", "$(P)top\n")
    (tree.epics / "ioc" / "config").mkdir()

    link_req_files()

    autosave = tree.epics / "autosave"
    assert sorted(p.name for p in autosave.iterdir()) == [
        "asyn_settings.req",
        "busyRecord_settings.req",
        "busy_settings.req",
        "top.req",
    ]
    # one that ibek-support gave is not replaced
    assert autosave.joinpath("busy_settings.req").resolve().parent == tree.module(
        "busy"
    )
    record = autosave / "busyRecord_settings.req"
    assert record.resolve() == clone / "db" / "busyRecord_settings.req"


@pytest.mark.parametrize("kind", ["other repo", "not a clone", "hand edited"])
def test_declared_clone_that_is_no_longer_the_module(work: Work, kind: str):
    """Checked again whenever it is reported or linked, not only when declared."""
    tree, clone, folder = work.tree, work.clone("busy"), work.tree.built("busy")
    tree.dev("support", "busy")
    work.recreate()
    if kind == "hand edited":
        # a clone of another module
        text = (tree.source / ".ibek-dev.yaml").read_text()
        work.own_clone("asyn")
        (tree.source / ".ibek-dev.yaml").write_text(
            text.replace(str(clone), str(work.clone("asyn")))
        )
    else:
        shutil.rmtree(clone)
        if kind == "other repo":
            work.own_clone("busy", "https://example.com/other/thing.git")
        else:
            write(clone / "README", "not a clone\n")
    tree.calls.clear()

    for command in ("status", "sync", "sync --build"):
        output = tree.dev(*command.split())
        assert "matches" not in output
        assert "busy: declared for development, and its clone cannot be" in output
    assert tree.calls == []
    assert folder.is_dir() and not folder.is_symlink()

    tree.dev("support", "--release", "busy")
    assert "matches" in tree.dev("sync", "--build")


def test_linked_clone_that_was_made_again(work: Work):
    """A fresh clone behind the link is not built: never a match."""
    tree, clone = work.tree, work.clone("busy")
    tree.dev("support", "busy")
    shutil.rmtree(clone)
    git(work.upstream, "clone", "--quiet", str(work.upstream / "busy"), str(clone))
    tree.calls.clear()

    for command in ("status", "sync"):
        output = tree.dev(command)
        assert "matches" not in output
        assert f"busy: its clone {clone} is not built" in output
        assert "rebuilds: busy, motor, then the IOC" in output
    assert tree.calls == []
    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]


def test_failed_build_of_a_clone_survives_a_new_stamp(work: Work):
    tree = work.tree
    tree.fail_on = "busy"
    tree.dev("support", "busy", code=2)
    # a stamp forgets what is pending; the clone still says it is not built
    tree.dev("stamp")
    output = tree.dev("status")
    assert "matches" not in output and "is not built" in output
    tree.fail_on = ""
    assert "matches" in tree.dev("sync", "--build")


@pytest.mark.parametrize("name", ["../ioc", "busy/", "/epics/ioc", ".", ".."])
def test_release_takes_only_module_names(work: Work, name: str):
    tree = work.tree
    tree.dev("support", "busy")

    output = tree.dev("support", "--release", name, code=1)
    assert f"{name}: not the name of a support module" in output
    assert (tree.epics / "ioc").is_symlink() and tree.built("busy").is_symlink()
    assert set(work.declarations()) == {"busy"}


def test_release_named_twice(work: Work):
    tree = work.tree
    tree.dev("support", "busy")
    output = tree.dev("support", "--release", "busy", "busy")
    assert output.count("removed the link") == 1
    assert "no longer declared" not in output


def test_support_will_not_clone_a_later_module_again(work: Work):
    """That removes a folder which nobody has been told of: sync --build first."""
    tree, folder = work.tree, work.tree.built("busy")
    edit = write(folder / "edit.c", "an edit")
    install = tree.module("busy") / "busy.install.yml"
    install.write_text(install.read_text().replace("R1-0", "main"))

    output = tree.dev("support", "asyn", code=1)
    assert f"busy must be cloned again, which removes {folder}" in output
    assert "run `ibek dev sync --build` for that first" in output
    assert edit.exists() and tree.calls == []
    assert not work.clone("asyn").exists() and work.declarations() == {}


def test_support_checks_every_module_before_cloning(work: Work):
    tree = work.tree
    (tree.module("motor") / "motor.install.yml").write_text("module: motor\n")
    tree.dev("stamp")

    output = tree.dev("support", "busy", "motor", code=1)
    assert "must set both module and version" in output
    assert not work.clone("busy").exists() and tree.calls == []


@pytest.mark.parametrize(
    "repo, message",
    [
        ('"{{ 1 / 0 }}"', "ZeroDivisionError"),
        ('""', "git_repo is ''"),
        ("--upload-pack=touch", "git_repo is '--upload-pack=touch'"),
    ],
)
def test_support_with_a_git_repo_that_cannot_be_cloned(
    work: Work, repo: str, message: str
):
    tree = work.tree
    (tree.module("busy") / "busy.install.yml").write_text(
        f"module: busy\nversion: R1-0\ngit_repo: {repo}\n"
    )
    tree.dev("stamp")
    output = tree.dev("support", "busy", code=1)
    assert message in output
    assert not work.clone("busy").exists()


def test_support_with_bad_defaults_in_the_ansible_role(work: Work):
    tree = work.tree
    defaults = tree.source / "ibek-support/_ansible/roles/support/vars/main.yml"
    write(defaults, "module: [\n")
    output = tree.dev("support", "busy", code=1)
    assert f"cannot read {defaults}" in output


def test_module_folder_that_is_a_file(work: Work):
    tree, folder = work.tree, work.tree.built("busy")
    shutil.rmtree(folder)
    write(folder, "not a folder")

    output = tree.dev("status")
    assert "matches" not in output
    assert f"busy: {folder} is a file, not a module folder" in output

    # replaced by the link to a clone
    assert "matches" in tree.dev("support", "busy")
    assert folder.resolve() == work.clone("busy")


def test_same_repo_with_doubled_slashes():
    assert clones.same_repo(
        "https://github.com/epics-modules//busy",
        "https://github.com/epics-modules/busy",
    )


def test_what_the_build_makes_is_named_and_hidden(work: Work):
    """Names that git patterns treat specially are hidden all the same."""
    tree, clone = work.tree, work.clone("busy")
    work.own_clone("busy")
    git(clone, "config", "status.showUntrackedFiles", "no")
    names = ["a[1]*.o", "#notes", "!bang", "trailing ", "sp ace.d"]
    ansible_sh = tree.ansible_sh

    def build(*words: str) -> None:
        ansible_sh(*words)
        if words == ("busy",):
            for name in names:
                write(clone / "O.linux" / "x", "")
                write(clone / name, "made")

    tree.ansible_sh = build  # type: ignore[method-assign]

    output = tree.dev("support", "busy")

    status = subprocess.run(
        ["git", "-C", str(clone), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert [line.strip() for line in status] == ["M configure/RELEASE"]
    notice = output[output.index("git does not show these paths") :]
    for name in [*names, "O.linux/", "lib/"]:
        assert f"    {name}\n" in notice


def test_autosave_order_is_kept_for_a_tree_with_no_links(tree: Tree):
    """The first of two files of one name is the one that glob("**") finds."""
    support = tree.epics / "support"
    write(support / "asyn" / "db" / "same.req", "asyn\n")
    write(support / "busy" / "db" / "same.req", "busy\n")
    (tree.epics / "ioc" / "config").mkdir()
    first = next(r for r in support.glob("**/*.req") if r.name == "same.req")

    link_req_files()

    assert (tree.epics / "autosave" / "same.req").resolve() == first


@pytest.mark.parametrize("command", ["sync --build", "support busy"])
def test_linked_clone_swapped_for_another_repo_is_not_built(work: Work, command: str):
    tree, clone = work.tree, work.clone("motor")
    tree.dev("support", "motor")
    shutil.rmtree(clone)
    work.own_clone("motor", "https://example.com/other/thing.git")
    write(tree.module("asyn") / "asyn.install.yml.orig", "a stray file")
    tree.calls.clear()

    assert "motor: declared for development, and its clone cannot be" in (
        tree.dev("status")
    )
    output = tree.dev(*command.split(), code=1)
    assert f"{clone} is not a clone of {work.upstream / 'motor'}" in output
    assert tree.ansible() == []


def test_git_clean_of_a_linked_clone_is_not_a_match(work: Work):
    tree, clone = work.tree, work.clone("busy")
    tree.dev("support", "busy")
    git(clone, "clean", "-fdxq")

    output = tree.dev("status")
    assert "matches" not in output and f"busy: its clone {clone} is not built" in output
    tree.calls.clear()
    assert "matches" in tree.dev("sync", "--build")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
    # the record of the build is out of git's sight too
    assert git(clone, "status", "--porcelain") == "M configure/RELEASE"


def test_support_of_a_module_whose_source_changed(work: Work):
    """Its folder is replaced by the clone: there is nothing to clone again."""
    tree = work.tree
    install = tree.module("busy") / "busy.install.yml"
    install.write_text(install.read_text().replace("R1-0", "main"))

    output = tree.dev("support", "busy")
    assert tree.ansible() == [["busy"], ["motor"], ["ioc"]]
    assert "force_clone" not in str(tree.calls) and "matches" in output
    assert git(work.clone("busy"), "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_support_checks_every_existing_clone_before_cloning(work: Work):
    tree = work.tree
    work.own_clone("busy", "https://example.com/other/thing.git")

    output = tree.dev("support", "asyn", "busy", code=1)
    assert "is not a clone of" in output
    assert not work.clone("asyn").exists() and tree.calls == []


def test_declaration_of_the_folder_that_the_image_builds(work: Work):
    tree, folder = work.tree, work.tree.built("busy")
    # the clone that ansible made there
    shutil.rmtree(folder)
    git(work.upstream, "clone", "--quiet", str(work.upstream / "busy"), str(folder))
    write(folder / "VERSION", "R1-0")
    write(tree.source / ".ibek-dev.yaml", f"support:\n  busy: {folder}\n")

    output = tree.dev("status")
    assert f"{folder} is in {tree.epics / 'support'}, where the image builds" in output
    # nothing to build, and the folder is left alone
    assert "matches" not in tree.dev("sync", "--build")
    write(tree.module("asyn") / "asyn.install.yml.orig", "a stray file")
    assert "where the image builds" in tree.dev("sync", "--build", code=1)
    assert folder.is_dir() and not folder.is_symlink()
    assert (folder / "VERSION").read_text() == "R1-0"


def test_reports_when_git_cannot_be_run(work: Work, monkeypatch):
    tree = work.tree
    tree.dev("support", "busy")
    monkeypatch.setenv("PATH", str(tree.epics / "no-bin"))

    output = tree.dev("status")
    assert "matches" not in output and "cannot run git" in output
    assert "move it away" not in output


def test_declaration_with_a_relative_path(work: Work, monkeypatch):
    tree, folder = work.tree, work.tree.built("busy")
    work.own_clone("busy")
    write(tree.source / ".ibek-dev.yaml", "support:\n  busy: busy\n")
    monkeypatch.chdir(work.workspaces)

    output = tree.dev("sync", "--build")
    assert "absolute path of its clone" in output and "matches" not in output
    assert folder.is_dir() and not folder.is_symlink() and tree.calls == []


def test_declared_module_linked_elsewhere_is_not_built(work: Work):
    tree, folder = work.tree, work.tree.built("busy")
    tree.dev("support", "busy")
    other = work.own_clone("motor")
    folder.unlink()
    folder.symlink_to(other)
    write(tree.module("asyn") / "asyn.install.yml.orig", "a stray file")
    tree.calls.clear()

    output = tree.dev("sync", "--build", code=1)
    assert f"busy cannot be built: {folder} is a link to {other}, not to" in output
    assert tree.calls == [] and not (other / "lib").exists()


def test_declared_clone_missing_with_an_earlier_module_to_build(work: Work):
    tree, clone = work.tree, work.clone("motor")
    tree.dev("support", "motor")
    shutil.rmtree(clone)
    write(tree.module("asyn") / "asyn.install.yml.orig", "a stray file")
    tree.calls.clear()

    output = tree.dev("sync", "--build", code=1)
    assert f"is a link to {clone}, which is missing" in output
    # in a container created again there is no link
    work.recreate()
    output = tree.dev("sync", "--build", code=1)
    assert f"its declared clone {clone} is missing" in output
    assert "move it away" not in output and tree.calls == []


def test_exclude_file_with_no_newline_at_its_end(work: Work):
    clone = work.own_clone("busy")
    exclude = clone / ".git" / "info" / "exclude"
    exclude.write_text("*.swp")
    write(clone / "notes.swp", "mine")

    work.tree.dev("support", "busy")

    assert exclude.read_text().splitlines()[:2] == [
        "*.swp",
        "# made by an ibek dev build",
    ]
    assert "notes.swp" not in git(clone, "status", "--porcelain")
