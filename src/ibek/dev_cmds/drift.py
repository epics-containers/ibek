"""
Compare the stamp with the live source tree, and bring the container level.

The ansible roles of ibek-support decide what is cloned, built and linked.
This module only chooses which modules to hand them, removes dangling links
and regenerates the schema.
"""

import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import typer

from ibek.globals import GLOBALS, IOC_SCHEMA_NAME

from .stamp import (
    Stamp,
    StampError,
    ansible_folder,
    ioc_sources,
    source,
    support_folder,
)


def run(command: list[str]) -> None:
    """Run a command, and stop with its exit code if it fails."""
    print("+ " + " ".join(command), flush=True)
    try:
        code = subprocess.run(command).returncode
    except OSError as error:
        typer.echo(f"ibek dev: {error}", err=True)
        code = 1
    if code != 0:
        typer.echo(f"ibek dev: failed: {' '.join(command)}", err=True)
        raise typer.Exit(code)


def ansible(module: str, *args: str) -> None:
    run([str(ansible_folder() / "ansible.sh"), module, *args])


@dataclass
class Drift:
    """What the container lacks, by the level of work that puts it right."""

    # level 1: modules whose definition files changed
    defs: list[str] = field(default_factory=list)
    # level 1: links in the definition folders that point at nothing
    dangling: list[Path] = field(default_factory=list)
    # level 2: why modules need a rebuild
    reasons: list[str] = field(default_factory=list)
    # level 2: the modules to rebuild, in Dockerfile order
    rebuild: list[str] = field(default_factory=list)
    # level 2: those of them whose source is the wrong one, with the folder
    # that is removed to clone each again
    force: dict[str, Path] = field(default_factory=dict)
    # level 2: those whose folder is a link, which is never removed
    links: dict[str, Path] = field(default_factory=dict)
    requirements: bool = False
    # level 3
    base: bool = False
    # why the IOC needs a build, or empty
    ioc: str = ""
    # what neither sync nor a rebuild puts right
    problems: list[str] = field(default_factory=list)


def dangling() -> list[Path]:
    folders = (GLOBALS.IBEK_DEFS, GLOBALS.PVI_DEFS, GLOBALS.AUTOSAVE)
    return [
        link
        for folder in folders
        if folder.is_dir()
        for link in sorted(folder.iterdir())
        if link.is_symlink() and not link.exists()
    ]


def ioc_reminder(stamp: Stamp) -> str:
    """Why `make` is needed in the IOC folder, or empty: `make` clears each."""
    binaries = list((GLOBALS.IOC_FOLDER / "bin").glob("*/ioc"))
    if not binaries:
        return "no IOC binary"
    built = max(binary.stat().st_mtime for binary in binaries)
    if stamp.rebuilt is not None and built < stamp.rebuilt:
        return "support modules were rebuilt after the IOC binary"
    if any(path.lstat().st_mtime > built for path in ioc_sources()):
        return "ioc source is newer than the IOC binary"
    return ""


def compare(stamp: Stamp, live: Stamp) -> Drift:
    """Work out what differs between the stamp and the live source tree."""
    drift = Drift(dangling=dangling())
    try:
        drift.ioc = ioc_reminder(stamp)
    except StampError as error:
        drift.problems.append(str(error))
    names, built = live.names(), stamp.names()
    first = len(names)

    def out_of_date(index: int, reason: str) -> None:
        nonlocal first
        first = min(first, index)
        drift.reasons.append(reason)

    if stamp.ansible != live.ansible:
        out_of_date(0, "ibek-support/_ansible changed: every module")

    for index, module in enumerate(live.modules):
        name, was = module.name, stamp.module(module.name)
        if module.build is None:
            drift.problems.append(
                f"{name}: the Dockerfile builds it, but {source()} does not "
                f"have one ibek-support*/{name} folder"
            )
        elif name in stamp.pending:
            out_of_date(index, f"{name}: rebuild not finished")
        elif was is None:
            out_of_date(index, f"{name}: not built in this container")
        elif was.source != module.source:
            out_of_date(index, f"{name}: version, repository or patch changed")
        elif was.build != module.build:
            out_of_date(index, f"{name}: build files changed")
        if was is not None and module.defs is not None and was.defs != module.defs:
            drift.defs.append(name)

        # Clone again only when install.yml asks for a source other than the
        # one in the module folder. With no folder there is nothing to remove,
        # and a link is someone's own folder: it is built as it is.
        if was and was.source and module.source and was.source != module.source:
            folder = support_folder(name)
            if folder is not None and folder.is_symlink():
                drift.links[name] = folder
            elif folder is not None and folder.exists():
                drift.force[name] = folder

    # A module added, moved or removed: rebuild from where the lists part. A
    # module with no ibek-support folder cannot be built, so it is not counted.
    missing = [module.name for module in live.modules if module.build is None]
    present = [name for name in names if name not in missing]
    had = [name for name in built if name not in missing]
    parts = next(
        (names.index(n) for i, n in enumerate(present) if had[i : i + 1] != [n]),
        first,
    )
    if parts < first:
        out_of_date(parts, "the Dockerfile's module list changed")
    removed = [name for name in built if name not in names]
    if removed:
        drift.problems.append(
            f"{', '.join(removed)}: not in the Dockerfile, and installed until "
            "this container is recreated from an image built without it"
        )

    drift.rebuild = [name for name in names[first:] if name not in missing]
    drift.force = {n: f for n, f in drift.force.items() if n in drift.rebuild}
    drift.links = {n: f for n, f in drift.links.items() if n in drift.rebuild}
    drift.requirements = stamp.requirements != live.requirements
    drift.base = stamp.base != live.base
    return drift


def report(drift: Drift) -> list[str]:
    """Describe the drift, with the command that puts each part right."""
    lines = []
    if drift.defs or drift.dangling:
        what = [f"definitions changed: {', '.join(drift.defs)}"] if drift.defs else []
        if drift.dangling:
            what.append(f"{len(drift.dangling)} dangling definition links")
        lines += ["; ".join(what), "    fix: ibek dev sync"]
    if drift.reasons or drift.requirements:
        lines.append("out of date:")
        lines += [f"    {reason}" for reason in drift.reasons]
        if drift.requirements:
            lines.append("    requirements.txt changed")
        if drift.rebuild:
            lines.append(f"    rebuilds: {', '.join(drift.rebuild)}, then the IOC")
        for name, folder in drift.force.items():
            lines.append(
                f"    clones {name} again: {folder} and edits in it are removed"
            )
        for name, folder in drift.links.items():
            lines.append(f"    {name}: {folder} is a link, built as it is")
        lines.append("    fix: ibek dev sync --build")
    if drift.base:
        lines.append(
            "base image changed (the Dockerfile's ARG and FROM lines): "
            "pull a newer developer image or rebuild it locally"
        )
    if drift.ioc:
        lines.append(f"IOC: {drift.ioc}: run `make` in {GLOBALS.IOC_FOLDER}")
    return lines + drift.problems


def schema() -> None:
    """Regenerate the IOC schema from the linked definition files."""
    output = str(GLOBALS.IBEK_DEFS / IOC_SCHEMA_NAME)
    run([sys.executable, "-m", "ibek", "ioc", "generate-schema", "--output", output])


def fix_defs(stamp: Stamp, live: Stamp, drift: Drift) -> None:
    """Level 1: link the definition files as they are now and remake the schema."""
    if drift.defs:
        ansible(",".join(drift.defs), "--tags", "runtime")
    for link in dangling():
        link.unlink()
    schema()
    for was in stamp.modules:
        now = live.module(was.name)
        # a module whose folder has gone lost its links: make them when it is back
        if now and (was.name in drift.defs or now.defs is None):
            was.defs = now.defs
    stamp.save()


def build(stamp: Stamp, live: Stamp, drift: Drift) -> None:
    """
    Level 2: build the out of date modules in Dockerfile order, then the IOC.

    The stamp records each step as it is done, so a build that fails part way
    is picked up by the next one.
    """
    modules, force = drift.rebuild, drift.force
    clone_task = ansible_folder() / "roles" / "support" / "tasks" / "clone.yml"
    if force and "force_clone" not in clone_task.read_text():
        typer.echo(
            f"ibek dev: {', '.join(force)} must be cloned again, which this "
            "ibek-support cannot do (no force_clone): update ibek-support",
            err=True,
        )
        raise typer.Exit(1)

    def record(name: str, source_only: bool = False) -> None:
        was, now = stamp.module(name), live.module(name)
        assert now is not None
        if source_only:
            assert was is not None
            was.source = now.source
        else:
            done = {m.name: m for m in stamp.modules} | {name: now}
            # in the order of the Dockerfile, then those it has dropped
            order = dict.fromkeys([*live.names(), *stamp.names()])
            stamp.modules = [done[n] for n in order if n in done]
            stamp.pending.remove(name)
        stamp.save()

    stamp.pending = list(dict.fromkeys([*stamp.pending, *modules]))
    stamp.ansible = live.ansible
    # the IOC binary is out of date from here until it is built again
    stamp.rebuilt = time.time()
    stamp.save()

    for name in modules:
        if name in force:
            # The clone is a step of its own, recorded before the build: a
            # build that fails is then retried on the source that is there,
            # with whatever was done to it, and not on a fresh clone.
            print(f"ibek dev: removing {force[name]} to clone {name} again")
            ansible(name, "--tags", "clone", "-e", "force_clone=true")
            record(name, source_only=True)
        elif name in drift.links:
            print(f"ibek dev: {drift.links[name]} is a link: it is left alone")
        ansible(name)
        record(name)

    ansible("ioc")
