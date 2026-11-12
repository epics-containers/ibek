"""
The stamp: a record of the source tree that a generic IOC image is built from.

``ibek dev stamp`` writes it at image build. In a devcontainer the host project
is mounted over the same source folder, so computing the stamp again there and
comparing the two shows what the container lacks.

Hashes cover file names and content only. File modes are left out and CRLF is
read as LF, so a git checkout on any host hashes the same as the image's copy.
"""

import fnmatch
import hashlib
import json
import os
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ibek.globals import GLOBALS

# version of the stamp file layout
SCHEMA = 1

# the files of an ibek-support module folder that are linked into the
# definition folders: these make up its defs hash, all its others the build hash
DEFS = ("*.ibek.support.yaml", "*.pvi.device.yaml", "*.req")
# names that tools leave behind and git does not track: in no hash. Any other
# file in a hashed folder counts.
JUNK = (
    ".git",
    ".ansible",
    "__pycache__",
    "*.pyc",
    "*build.log",
    "*~",
    "*.swp",
    ".DS_Store",
)


class StampError(Exception):
    """The stamp, or the tree it describes, cannot be read."""


def source() -> Path:
    """The generic IOC source: the image's copy, or the host project mount."""
    return GLOBALS.EPICS_ROOT / "generic-source"


def stamp_file() -> Path:
    return GLOBALS.EPICS_ROOT / "dev-stamp.json"


def ansible_folder() -> Path:
    return source() / "ibek-support" / "_ansible"


@dataclass
class Module:
    name: str
    defs: str | None = None
    build: str | None = None
    # what decides the source that is cloned
    source: str | None = None


@dataclass
class Stamp:
    # the Dockerfile's ARG and FROM lines
    base: str
    requirements: str
    ansible: str
    # in Dockerfile order, then any that the Dockerfile has dropped
    modules: list[Module]
    # modules whose rebuild has started and not finished
    pending: list[str] = field(default_factory=list)
    # when ibek dev last started to rebuild modules in this container
    rebuilt: float | None = None

    def names(self) -> list[str]:
        return [module.name for module in self.modules]

    def module(self, name: str) -> Module | None:
        return next((m for m in self.modules if m.name == name), None)

    def save(self) -> None:
        text = json.dumps({"schema": SCHEMA, **asdict(self)}, indent=2)
        # written whole or not at all
        temporary = stamp_file().with_name(stamp_file().name + ".tmp")
        try:
            temporary.write_text(text + "\n")
            temporary.replace(stamp_file())
        except OSError as error:
            raise StampError(f"cannot write {stamp_file()}: {error}") from error


def load() -> Stamp | None:
    """Read the stamp file: None when the image has none."""
    if not stamp_file().exists():
        return None
    try:
        data = json.loads(stamp_file().read_text())
        schema = data.pop("schema", None)
        if schema != SCHEMA:
            raise StampError(
                f"{stamp_file()} has schema {schema}, this ibek reads {SCHEMA}: "
                "nothing to compare"
            )
        modules = [Module(**module) for module in data.pop("modules")]
        return Stamp(modules=modules, **data)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise StampError(f"cannot read {stamp_file()}: {error}") from error


def _files(
    root: Path, skip: Callable[[str], bool] | None = None
) -> Iterator[tuple[str, Path]]:
    """
    Yield (relative path, path) for each file below root, in a fixed order.

    Leaves out JUNK names, and each relative path that skip is true for.
    """

    def scan(folder: Path, prefix: str) -> Iterator[tuple[str, Path]]:
        try:
            entries = sorted(os.scandir(folder), key=lambda e: e.name)
        except OSError as error:
            raise StampError(f"cannot read {folder}: {error.strerror}") from error
        for entry in entries:
            path = prefix + entry.name
            if any(fnmatch.fnmatchcase(entry.name, junk) for junk in JUNK):
                continue
            if skip is not None and skip(path):
                continue
            if entry.is_dir(follow_symlinks=False):
                yield from scan(Path(entry.path), path + "/")
            else:
                yield path, Path(entry.path)

    if root.is_dir():
        yield from scan(root, "")


def _hash(files: Iterable[tuple[str, Path]]) -> str:
    total = hashlib.sha256()
    for name, path in files:
        try:
            if path.is_symlink():
                content = b"link " + os.readlink(path).encode()
            else:
                content = path.read_bytes().replace(b"\r\n", b"\n")
        except OSError as error:
            raise StampError(f"cannot read {path}: {error.strerror}") from error
        total.update(name.encode() + b"\0" + hashlib.sha256(content).digest())
    return total.hexdigest()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def module_folder(name: str) -> Path | None:
    """The one ibek-support*/<name> folder, as the ansible find role picks it."""
    found = list(source().glob(f"ibek-support*/{name}"))
    return found[0] if len(found) == 1 else None


def _install(name: str) -> dict | None:
    """A module's install.yml: None when it is missing or unreadable."""
    folder = module_folder(name)
    if folder is None:
        return None
    try:
        values = YAML(typ="safe").load(folder / f"{name}.install.yml")
    except (OSError, YAMLError):
        return None
    return values if isinstance(values, dict) else None


def _source(name: str) -> str | None:
    """
    Hash what a module's install.yml says to clone: None when it is unreadable.

    A change here means the source in /epics/support is the wrong one. Any
    other change to the folder is built with the source that is there.
    """
    keys = ("module", "version", "organization", "git_repo", "recursive", "patch_file")
    folder, values = module_folder(name), _install(name)
    if folder is None or values is None:
        return None
    total = json.dumps([values.get(key) for key in keys], default=str).encode()
    patch = values.get("patch_file")
    patch = patch.get("path") if isinstance(patch, dict) else None
    if patch and (folder / str(patch)).is_file():
        total += (folder / str(patch)).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(total).hexdigest()


def support_folder(name: str) -> Path | None:
    """Where the ansible support role clones and builds a module."""
    values = _install(name)
    if values is None:
        return None
    # the role's default, unless install.yml names a folder outright
    local_path = values.get("local_path")
    if isinstance(local_path, str) and "{{" not in local_path:
        return Path(local_path)
    return GLOBALS.SUPPORT / str(values.get("module") or name)


def _module(name: str) -> Module:
    folder = module_folder(name)
    if folder is None:
        return Module(name)

    def is_def(path: str) -> bool:
        return "/" not in path and any(fnmatch.fnmatchcase(path, p) for p in DEFS)

    files = list(_files(folder))
    return Module(
        name,
        defs=_hash(f for f in files if is_def(f[0])),
        build=_hash(f for f in files if not is_def(f[0])),
        source=_source(name),
    )


def ioc_sources() -> Iterator[Path]:
    """The files that `make` in the IOC folder builds the IOC binary from."""
    ioc = source() / "ioc"
    if (ioc / "Makefile").is_file():
        yield ioc / "Makefile"
    for folder in ("configure", "iocApp"):
        for _, path in _files(
            ioc / folder,
            lambda path: fnmatch.fnmatchcase(path.rsplit("/", 1)[-1], "O.*"),
        ):
            yield path


def _read(path: Path) -> str:
    if not path.is_file():
        raise StampError(f"{path} not found: nothing to compare")
    try:
        return path.read_text()
    except (OSError, ValueError) as error:
        raise StampError(f"cannot read {path}: {error}") from error


def compute() -> Stamp:
    """Describe the tree at the generic IOC source folder."""
    dockerfile = _read(source() / "Dockerfile").splitlines()
    requirements = _read(source() / "requirements.txt")
    # a submodule that is not checked out is an empty folder
    support = sorted(source().glob("ibek-support*"))
    empty = [f for f in support if f.is_dir() and not any(f.iterdir())]
    if empty or not ansible_folder().is_dir():
        raise StampError(
            f"{(empty or [source() / 'ibek-support'])[0]} is not checked out: "
            "run `git submodule update --init` in the project on the host"
        )

    # the module list, as the ansible all_support role reads it
    matches = (re.match(r"RUN *ansible.sh ([^ ]*)", line) for line in dockerfile)
    # a module named twice is one module, where it is first named
    names = list(dict.fromkeys(match.group(1) for match in matches if match))
    base = [" ".join(line.split()) for line in dockerfile]
    base = [line for line in base if line.startswith(("ARG ", "FROM "))]

    return Stamp(
        base=_hash_text("\n".join(base)),
        requirements=_hash_text(requirements.replace("\r\n", "\n")),
        # the find role writes into vars/
        ansible=_hash(_files(ansible_folder(), lambda path: path == "vars")),
        modules=[_module(name) for name in names if name not in ("", "ioc")],
    )
