"""
Support modules built from a clone on the host instead of the image's copy.

``ibek dev support <module>`` declares each one in ``.ibek-dev.yaml`` in the
generic IOC source folder, which is on the host: the declaration outlives the
container, so ``ibek dev sync --build`` can apply it to another one.
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Template, TemplateError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .stamp import StampError, ansible_folder, module_folder, source

# where a devcontainer mounts the folder that holds the host's projects
WORKSPACES = Path("/workspaces")


def valid_name(name: str) -> bool:
    """Whether a module name is a plain folder name, as the Dockerfile has it."""
    return bool(re.fullmatch(r"[A-Za-z0-9_+-][A-Za-z0-9_.+-]*", name))


def declarations_file() -> Path:
    return source() / ".ibek-dev.yaml"


def declared() -> dict[str, Path]:
    """The modules to build from a clone, with the folder of each clone."""
    path = declarations_file()
    shape = (
        f"{path} holds `support:` with a `<module>: <folder of its clone>` "
        "line for each module"
    )
    try:
        if not path.exists():
            return {}
        data = YAML(typ="safe").load(path.read_text())
    except (OSError, ValueError, YAMLError) as error:
        raise StampError(f"cannot read {path}: {shape}") from error
    modules = data.get("support") if isinstance(data, dict) else data
    if modules is None:
        return {}
    if not isinstance(modules, dict) or not all(
        isinstance(name, str) and isinstance(clone, str) and clone
        for name, clone in modules.items()
    ):
        raise StampError(f"cannot read {path}: {shape}")
    return {name: Path(clone) for name, clone in modules.items()}


def declare(name: str, clone: Path | None) -> None:
    """Record that a module is built from clone, or with None that it is not."""
    modules = {module: str(path) for module, path in declared().items()}
    if (clone is None and name not in modules) or modules.get(name) == str(clone):
        return
    modules.pop(name, None)
    if clone is not None:
        modules[name] = str(clone)
    path = declarations_file()
    # written whole or not at all
    temporary = path.with_name(path.name + ".tmp")
    try:
        if modules:
            with temporary.open("w") as stream:
                stream.write(
                    "# Support modules built from a clone: see `ibek dev support`\n"
                )
                YAML().dump({"support": modules}, stream)
            temporary.replace(path)
        else:
            path.unlink(missing_ok=True)
    except OSError as error:
        raise StampError(f"cannot write {path}: {error}") from error


@dataclass
class Install:
    """What a module's install.yml says about its source."""

    git_repo: str
    version: str
    recursive: bool
    # the patch that the ansible role applies to a clone that it makes
    patch: Path | None


def install(name: str, options: list[str]) -> Install:
    """
    Read a module's install.yml over the defaults of the ansible support role.

    options are those of the module's Dockerfile line: `-v` gives the version.
    """
    folder = module_folder(name)
    path = folder / f"{name}.install.yml" if folder else None
    if path is None or not path.is_file():
        raise StampError(
            f"{name}: no ibek-support*/{name}/{name}.install.yml in {source()}"
        )
    assert folder is not None
    defaults = ansible_folder() / "roles" / "support" / "vars" / "main.yml"
    yaml = YAML(typ="safe")
    values: dict = {}
    try:
        if defaults.is_file():
            values.update(yaml.load(defaults.read_text()) or {})
    except (OSError, ValueError, TypeError, YAMLError) as error:
        raise StampError(f"cannot read {defaults}: {error}") from error
    try:
        values.update(yaml.load(path.read_text()) or {})
        version = values.get("version")
        if len(options) == 2:
            version = options[1]
        elif options:
            version = options[0].removeprefix("-v")
        if not values.get("module") or not version:
            raise StampError("it must set both module and version")
        values.setdefault("organization", "https://github.com/epics-modules")
        values.setdefault("git_repo", "{{ organization.rstrip('/') }}/{{ module }}")
        for key in ("organization", "git_repo"):
            try:
                values[key] = Template(str(values[key])).render(values)
            except Exception as error:
                # a template can fail in any way that Python can
                raise StampError(f"{key}: {error!r}") from error
        if not values["git_repo"] or values["git_repo"].startswith("-"):
            raise StampError(f"git_repo is {values['git_repo']!r}")
        patch = values.get("patch_file")
        patch = patch.get("path") if isinstance(patch, dict) else None
        return Install(
            git_repo=values["git_repo"],
            version=str(version),
            recursive=str(values.get("recursive")).lower() in ("true", "yes", "1"),
            patch=folder / str(patch) if patch else None,
        )
    except (
        OSError,
        ValueError,
        TypeError,
        YAMLError,
        TemplateError,
        StampError,
    ) as error:
        raise StampError(f"cannot read {path}: {error}") from error


def git(folder: Path, *args: str, show: bool = False) -> str:
    """
    Run git in a folder and return what it printed.

    With show, the command and what it prints go to the terminal instead.
    """
    command = ["git", "-C", str(folder), *args]
    if show:
        print("+ " + " ".join(command), flush=True)
    try:
        done = subprocess.run(
            command,
            stdout=None if show else subprocess.PIPE,
            stderr=None if show else subprocess.PIPE,
            text=True,
            errors="replace",
        )
    except OSError as error:
        raise StampError(f"cannot run git: {error}") from error
    if done.returncode != 0:
        said = "" if show else f": {done.stderr.strip()}"
        raise StampError(f"failed: {' '.join(command)}{said}")
    return "" if show else done.stdout


def same_repo(one: str, other: str) -> bool:
    """Whether two git URLs name the same repository, however it is reached."""

    def normal(url: str) -> str:
        url = url.strip().lower().rstrip("/").removesuffix(".git").rstrip("/")
        # git@host:path, the scp form of ssh
        scp = re.fullmatch(r"(?:[^@/:]+@)?([^/:]+):(?!//)(.+)", url)
        if scp:
            return f"{scp.group(1)}/{scp.group(2).lstrip('/')}"
        # scheme://user@host:port/path
        url = re.sub(r"^[a-z][a-z0-9+.-]*://", "", url)
        host, _, path = url.partition("/")
        host = host.rsplit("@", 1)[-1].split(":")[0]
        return f"{host}/{path}"

    def tidy(url: str) -> str:
        host, _, path = normal(url).partition("/")
        return host + "/" + re.sub("/+", "/", path).strip("/")

    return tidy(one) == tidy(other)


def check(name: str, info: Install, clone: Path, quiet: bool = False) -> None:
    """
    Refuse a clone that is not of the module's repository.

    Its branch and version are its owner's: say when they are not the version
    that install.yml builds, and leave them alone.
    """
    try:
        top = Path(git(clone, "rev-parse", "--show-toplevel").strip())
        why = "" if top.samefile(clone) else f"it is a folder of {top}"
    except (StampError, OSError) as error:
        why = str(error)
    if why:
        raise StampError(
            f"{clone} exists and is not a git clone that can be used ({why}): "
            f"move it away, or clone {info.git_repo} there"
        )
    # each line is a remote's name, its URL and whether it fetches or pushes
    remotes = [line.split() for line in git(clone, "remote", "-v").splitlines()]
    urls = list(dict.fromkeys(words[1] for words in remotes if len(words) > 1))
    if not any(same_repo(url, info.git_repo) for url in urls):
        raise StampError(
            f"{clone} is not a clone of {info.git_repo}, which {name}.install.yml "
            f"builds: its remotes are {', '.join(urls) or 'none'}"
        )

    def commit(revision: str) -> str:
        try:
            return git(clone, "rev-parse", "--verify", "--quiet", revision).strip()
        except StampError:
            return ""

    head = commit("HEAD^{commit}")
    if quiet:
        return
    if not head or head != commit(f"{info.version}^{{commit}}"):
        try:
            at = git(clone, "rev-parse", "--abbrev-ref", "HEAD").strip()
            if at in ("", "HEAD"):
                at = git(clone, "describe", "--tags", "--always").strip()
        except StampError:
            at = "no commit"
        print(
            f"ibek dev: {clone} is at {at}, not at the {info.version} of "
            f"{name}.install.yml: it is built as it is",
            flush=True,
        )


def make(name: str, info: Install, clone: Path) -> None:
    """Clone the module's repository, whole, at the version of install.yml."""
    try:
        clone.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise StampError(f"cannot make {clone.parent}: {error}") from error
    git(clone.parent, "clone", "--", info.git_repo, str(clone), show=True)
    try:
        git(
            clone,
            "-c",
            "advice.detachedHead=false",
            "checkout",
            info.version,
            show=True,
        )
        if info.recursive:
            git(clone, "submodule", "update", "--init", "--recursive", show=True)
    except StampError as error:
        raise StampError(
            f"{error}. {clone} is left as it is: check out the version to "
            f"build there and run `ibek dev support {name}` again"
        ) from error


def linked(folder: Path, clone: Path) -> bool:
    """Whether the folder a module is built in is a link to this clone."""
    return points_at(folder, clone) and clone.is_dir()


def points_at(folder: Path, clone: Path) -> bool:
    """Whether a folder is a link to where this clone is, or would be."""
    return folder.is_symlink() and os.path.realpath(folder) == os.path.realpath(clone)


def target(folder: Path) -> str:
    """Where a link points, as it is written."""
    try:
        return os.readlink(folder)
    except OSError:
        return "nowhere"


def link(folder: Path, clone: Path) -> None:
    """Remove the module that is in the container and link the clone there."""
    try:
        unlink(folder)
        if folder.is_dir():
            shutil.rmtree(folder)
        elif folder.exists():
            folder.unlink()
        folder.parent.mkdir(parents=True, exist_ok=True)
        folder.symlink_to(clone)
    except OSError as error:
        raise StampError(f"cannot link {folder} to {clone}: {error}") from error


def unlink(folder: Path) -> bool:
    """Remove a link and leave what it points at. False when it is no link."""
    try:
        if not folder.is_symlink():
            return False
        folder.unlink()
        return True
    except OSError as error:
        raise StampError(f"cannot remove the link {folder}: {error}") from error


# a file in a clone's git folder, out of git's sight, that says the clone was
# built after it was linked: a clone made again or a build that stopped has none
BUILT = "ibek-dev-built"


def marker(clone: Path) -> Path:
    path = Path(git(clone, "rev-parse", "--git-path", BUILT).strip())
    return path if path.is_absolute() else clone / path


def built(clone: Path) -> bool:
    """Whether a build of the clone finished, as far as ibek dev knows."""
    try:
        return marker(clone).is_file()
    except (StampError, OSError):
        return False


def mark(clone: Path, done: bool) -> None:
    """Record that a build of the clone starts, or that it finished."""
    try:
        if done:
            marker(clone).write_text("built by ibek dev\n")
        else:
            marker(clone).unlink(missing_ok=True)
    except OSError as error:
        raise StampError(f"cannot record the build of {clone}: {error}") from error


# the untracked paths of a clone, and when each tracked file that differs
# from its commit was last written: None for one that is removed
Changes = tuple[set[str], dict[str, int | None]]


def changes(clone: Path) -> Changes:
    """What `git status` shows in a clone."""
    # every untracked file, whatever the clone's settings; what is made inside
    # a submodule is the submodule's to show
    status = git(
        clone,
        "status",
        "--porcelain",
        "-z",
        "--untracked-files=normal",
        "--ignore-submodules=untracked",
    ).split("\0")
    untracked: set[str] = set()
    edited: dict[str, int | None] = {}
    entries = iter(status)
    for entry in entries:
        code, path = entry[:2], entry[3:]
        if code == "??":
            untracked.add(path)
        elif path:
            try:
                edited[path] = (clone / path).lstat().st_mtime_ns
            except OSError:
                edited[path] = None
            if "R" in code or "C" in code:
                # the path that it was renamed or copied from
                next(entries, None)
    return untracked, edited


def before_build(clone: Path) -> Changes | None:
    """What git shows in a clone before a build: None when it cannot say."""
    try:
        return changes(clone)
    except StampError as error:
        print(f"ibek dev: cannot read the git status of {clone}: {error}", flush=True)
        return None


def after_build(clone: Path, before: Changes | None) -> None:
    """
    Deal with what a build did to a clone. Never an error.

    What the build made is listed in the clone's own .git/info/exclude, so
    git does not show it. Tracked files that the build edited are named: they
    show in `git status`, as the developer's own edits to them must.
    """
    if before is None:
        return
    try:
        untracked, edited = changes(clone)
        made = sorted(untracked - before[0])
        if made:
            exclude = Path(
                git(clone, "rev-parse", "--git-path", "info/exclude").strip()
            )
            exclude = exclude if exclude.is_absolute() else clone / exclude
            exclude.parent.mkdir(parents=True, exist_ok=True)
            # a name that a pattern cannot hold stays in sight
            made = [path for path in made if "\n" not in path]
            with exclude.open("a") as stream:
                stream.write("# made by an ibek dev build\n")
                for path in made:
                    pattern = re.sub(r"([\\*?\[!#])", r"\\\1", path)
                    pattern = re.sub(r" (?= *$)", r"\\ ", pattern)
                    stream.write("/" + pattern + "\n")
            print(
                f"ibek dev: git does not show these paths that the build made in "
                f"{clone}: they are listed in {exclude}",
                flush=True,
            )
            for path in made:
                print(f"    {path}", flush=True)

        # written during the build: one that differed before it has a new time
        files = sorted(
            path
            for path, written in edited.items()
            if path not in before[1] or before[1][path] != written
        )
        if files:
            print(
                f"ibek dev: the build edited these tracked files of {clone}, "
                "to build it in this container. They show in `git status`: "
                "do not commit those edits.",
                flush=True,
            )
            for path in files:
                print(f"    {path}", flush=True)
    except (StampError, OSError) as error:
        print(f"ibek dev: cannot tidy {clone} after its build: {error}", flush=True)
