"""
Tests for the `ibek dev` commands.

Each test works on a generic IOC tree in a temporary folder. Every command that
ibek would run is recorded, and a stand-in does to the tree what ansible.sh
does to a container: it removes, clones and builds module folders.
"""

import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import typer
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from ibek.__main__ import cli
from ibek.dev_cmds import drift
from ibek.dev_cmds.stamp import compute, load
from ibek.globals import GLOBALS

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

    def ansible_sh(self, module: str, *args: str) -> None:
        """Do what ansible.sh does with these arguments."""
        folder = self.built(module)
        install = (
            self.module(module) / f"{module}.install.yml" if module != "ioc" else None
        )

        def clone() -> None:
            assert install is not None
            version = install.read_text().split("version: ")[1].split()[0]
            write(folder / "VERSION", version)

        if "--tags" in args and "clone" in args:
            # the clone tasks: with force_clone the folder is removed first
            if "force_clone=true" in args and folder.exists():
                shutil.rmtree(folder)
            if not folder.exists():
                clone()
        elif "--tags" in args:
            # the runtime tasks: link the definition files of each module
            assert args == ("--tags", "runtime")
            for name in module.split(","):
                for target in self.module(name).iterdir():
                    for defs, pattern in LINKS:
                        link = self.epics / defs / target.name
                        if target.match(pattern) and not link.is_symlink():
                            link.symlink_to(target)
        else:
            # every task: an existing folder is not cloned again
            assert args == ()
            if module != "ioc" and not folder.exists():
                clone()
            if self.fail_on == module:
                raise typer.Exit(2)
            if module == "ioc":
                self.make()
            else:
                write(folder / "lib" / f"lib{module}.a", "built")

    def ansible(self) -> list[list[str]]:
        """The arguments of each ansible.sh call."""
        return [call[1:] for call in self.calls if call[0].endswith("/ansible.sh")]

    def dev(self, *args: object, code: int = 0) -> str:
        """Run `ibek dev ...` and return what it printed."""
        result = runner.invoke(cli, ["dev", *(str(arg) for arg in args)])
        assert result.exit_code == code, result.output
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
    assert set(stamp["modules"][0]) == {"name", "defs", "build", "source"}
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
    assert "removing" not in output and "matches" in output
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
    assert "Run `ibek dev sync --build` again if more remains" in output
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
    assert "Run `ibek dev sync --build` again if more remains" in output
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


def test_level_2_needs_force_clone_in_ibek_support(tree: Tree):
    ansible = tree.source / "ibek-support" / "_ansible"
    write(ansible / "roles" / "support" / "tasks" / "clone.yml", "- name: Clone\n")
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
