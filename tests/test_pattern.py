"""
Tests for the ``ibek pattern`` runtime-support vendoring subsystem.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ibek.__main__ import cli
from ibek.globals import IOC_SCHEMA_NAME, RUNTIME_LOCK_NAME
from ibek.pattern_cmds import schema, vendor
from ibek.pattern_cmds.lock import (
    RuntimeLock,
    comment_prefix,
    file_hash,
    stamp_content,
    vendored_header,
)
from ibek.pattern_cmds.schema import (
    generate_instance_schema,
    generate_schema_dict,
    merge_entities,
    resolve_image_ref,
)
from ibek.pattern_cmds.sources import parse_ref

runner = CliRunner()

SUPPORT_HEADER = "# yaml-language-server: $schema=../schemas/ibek.support.schema.json"
MYDEVICE_SUPPORT = f"""{SUPPORT_HEADER}

module: mydevice

entity_models:
  - name: mydevice
    description: a test device
    parameters:
      name:
        type: id
        description: identifier
      P:
        type: str
        description: pv prefix
"""
MYDEVICE_PROTO = 'Terminator = CR LF;\ngetX { out "X?"; in "%f"; }\n'


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """A local pattern library with a single ``mydevice`` pattern."""
    pattern = tmp_path / "lib" / "mydevice"
    pattern.mkdir(parents=True)
    (pattern / "mydevice.ibek.support.yaml").write_text(MYDEVICE_SUPPORT)
    (pattern / "mydevice.proto").write_text(MYDEVICE_PROTO)
    return tmp_path / "lib"


def make_instance(root: Path, image: str = "REPLACE_WITH_IMAGE_URI") -> Path:
    """Create a minimal IOC instance folder."""
    instance = root / "bl01t-ea-test-01"
    (instance / "config").mkdir(parents=True)
    (instance / "values.yaml").write_text(f"ioc-instance:\n  image: {image}\n")
    (instance / "config" / "ioc.yaml").write_text(
        "# yaml-language-server: $schema=/epics/ibek-defs/ioc.schema.json\n"
        "ioc_name: test\nentities: []\n"
    )
    return instance


# --------------------------------------------------------------------------- #
# header / hashing
# --------------------------------------------------------------------------- #
def test_vendored_header_deterministic():
    src = "github.com/epics-containers/ibek-runtime-streamdevice"
    header = vendored_header(Path("x.proto"), src, "1.0.0")
    assert header == f"# Vendored from {src}@1.0.0 — DO NOT EDIT"
    # deterministic: same inputs -> identical bytes
    a = stamp_content(Path("x.proto"), b"body\n", src, "1.0.0")
    b = stamp_content(Path("x.proto"), b"body\n", src, "1.0.0")
    assert a == b
    assert a.startswith(header.encode())
    assert a.endswith(b"body\n")


def test_comment_prefix_default():
    assert comment_prefix(Path("a.proto")) == "#"
    assert comment_prefix(Path("a.weirdext")) == "#"


# --------------------------------------------------------------------------- #
# add / lock
# --------------------------------------------------------------------------- #
def test_add_vendors_files_with_header_and_lock(tmp_path: Path, library: Path):
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))

    proto = instance / "config" / "mydevice.proto"
    support = instance / "config" / "mydevice.ibek.support.yaml"
    assert proto.exists() and support.exists()
    # real files, not symlinks
    assert not proto.is_symlink()
    # header injected at the top, original content preserved below
    text = proto.read_text()
    assert text.startswith("# Vendored from ")
    assert "@1.0.0 — DO NOT EDIT" in text.splitlines()[0]
    assert "getX" in text

    lock = RuntimeLock(instance / RUNTIME_LOCK_NAME)
    assert set(lock.patterns) == {"mydevice"}
    entry = lock.patterns["mydevice"]
    assert entry.version == "1.0.0"
    assert "ibek-runtime-streamdevice" not in entry.source  # local source label
    # recorded hash matches the bytes on disk (header included)
    assert entry.files["mydevice.proto"] == file_hash(proto.read_bytes())
    assert set(entry.files) == {"mydevice.proto", "mydevice.ibek.support.yaml"}


# --------------------------------------------------------------------------- #
# check / dirty-state machine
# --------------------------------------------------------------------------- #
def test_check_pristine_passes(tmp_path: Path, library: Path):
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))
    result = vendor.check(instance)
    assert result.ok
    assert not result.failures


def test_check_detects_drift(tmp_path: Path, library: Path):
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))
    proto = instance / "config" / "mydevice.proto"
    proto.write_text(proto.read_text() + "# local hack\n")

    result = vendor.check(instance)
    assert not result.ok
    assert any("mydevice.proto" in f and "mismatch" in f for f in result.failures)

    # --allow-dirty downgrades the failure to a warning
    relaxed = vendor.check(instance, allow_dirty=True)
    assert relaxed.ok
    assert relaxed.warnings


def test_check_missing_file_fails(tmp_path: Path, library: Path):
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))
    (instance / "config" / "mydevice.proto").unlink()
    result = vendor.check(instance)
    assert not result.ok
    assert any("missing" in f for f in result.failures)


def test_check_respects_dirty_marker(tmp_path: Path, library: Path):
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))
    proto = instance / "config" / "mydevice.proto"
    proto.write_text(proto.read_text() + "# JIRA-123 relay fix\n")

    lock = RuntimeLock(instance / RUNTIME_LOCK_NAME)
    lock.patterns["mydevice"].files["mydevice.proto"] = "DIRTY # JIRA-123 relay fix"
    lock.save()

    result = vendor.check(instance)
    assert result.ok  # dirty marker is not a failure
    assert any("DIRTY" in w for w in result.warnings)


# --------------------------------------------------------------------------- #
# update / restore
# --------------------------------------------------------------------------- #
def test_update_moves_version(tmp_path: Path, library: Path):
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))
    # change the library content and re-vendor at a new version
    (library / "mydevice" / "mydevice.proto").write_text(MYDEVICE_PROTO + "getY {}\n")
    vendor.update("mydevice", instance, version="2.0.0", source_override=str(library))

    lock = RuntimeLock(instance / RUNTIME_LOCK_NAME)
    assert lock.patterns["mydevice"].version == "2.0.0"
    proto = instance / "config" / "mydevice.proto"
    assert "getY" in proto.read_text()
    assert "@2.0.0 — DO NOT EDIT" in proto.read_text().splitlines()[0]
    assert vendor.check(instance).ok


def test_update_prunes_orphaned_files(tmp_path: Path, library: Path):
    """A file dropped by the new version must leave neither disk nor lock residue."""
    instance = make_instance(tmp_path)
    # give the pattern a nested file so we also exercise empty-dir pruning
    (library / "mydevice" / "db").mkdir()
    (library / "mydevice" / "db" / "extra.db").write_text('record(ai, "X") {}\n')
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))
    nested = instance / "config" / "db" / "extra.db"
    assert nested.exists()

    # the new version drops the nested db file entirely
    (library / "mydevice" / "db" / "extra.db").unlink()
    vendor.update("mydevice", instance, version="2.0.0", source_override=str(library))

    assert not nested.exists()  # orphan removed from disk
    assert not nested.parent.exists()  # now-empty config/db/ pruned
    lock = RuntimeLock(instance / RUNTIME_LOCK_NAME)
    assert "db/extra.db" not in lock.patterns["mydevice"].files  # gone from the lock
    assert set(lock.patterns["mydevice"].files) == {
        "mydevice.proto",
        "mydevice.ibek.support.yaml",
    }
    assert vendor.check(instance).ok


def test_restore_reverts_local_edit(tmp_path: Path, library: Path):
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))
    proto = instance / "config" / "mydevice.proto"
    proto.write_text("corrupted\n")
    assert not vendor.check(instance).ok

    vendor.restore("mydevice", instance)
    assert vendor.check(instance).ok
    assert "getX" in proto.read_text()


# --------------------------------------------------------------------------- #
# qualified-name parsing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text, library, name, version",
    [
        ("lakeshore340", None, "lakeshore340", None),
        ("lakeshore340@1.2", None, "lakeshore340", "1.2"),
        ("lib:dev@0.1.0", "lib", "dev", "0.1.0"),
        (
            "ibek-runtime-support:detectorPlugins@2025.1",
            "ibek-runtime-support",
            "detectorPlugins",
            "2025.1",
        ),
    ],
)
def test_parse_ref(text, library, name, version):
    ref = parse_ref(text)
    assert (ref.library, ref.name, ref.version) == (library, name, version)


# --------------------------------------------------------------------------- #
# image ref resolution
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "image, expected",
    [
        (
            "ghcr.io/epics-containers/ioc-adsimdetector-runtime:2025.11.1",
            ("epics-containers", "ioc-adsimdetector", "2025.11.1"),
        ),
        (
            "ghcr.io/epics-containers/ioc-streamdevice-developer:1.0",
            ("epics-containers", "ioc-streamdevice", "1.0"),
        ),
        (
            "ghcr.io/myorg/ioc-foo-rtems-beatnik-runtime:3.2.1",
            ("myorg", "ioc-foo", "3.2.1"),
        ),
    ],
)
def test_resolve_image_ref(image, expected):
    assert resolve_image_ref(image) == expected


# --------------------------------------------------------------------------- #
# schema merge
# --------------------------------------------------------------------------- #
def test_merge_entities_grafts_new_types(samples: Path):
    support = sorted((samples / "support").glob("*.ibek.support.yaml"))
    base = generate_schema_dict([support[0]])
    before = set(base["properties"]["entities"]["items"]["discriminator"]["mapping"])
    merged = merge_entities(base, [support[1]])
    mapping = merged["properties"]["entities"]["items"]["discriminator"]["mapping"]
    after = set(mapping)
    added = after - before
    assert added  # new entity types grafted in
    # every new mapping target resolves to a $def that now exists
    for disc in added:
        ref = mapping[disc].split("/")[-1]
        assert ref in merged["$defs"]
    # built-ins are not duplicated in oneOf
    one_of = merged["properties"]["entities"]["items"]["oneOf"]
    refs = [o["$ref"] for o in one_of]
    assert len(refs) == len(set(refs))


def test_merge_entities_byte_stable_across_hashseed(samples: Path):
    """Merge output must not depend on PYTHONHASHSEED.

    The per-instance ioc.schema.json is committed and CI/pre-commit re-generate
    it and diff-fail on drift, so the merge must be byte-stable across processes
    (set/closure iteration order must not leak into the output).
    """
    support = sorted((samples / "support").glob("*.ibek.support.yaml"))
    script = (
        "import json;"
        "from pathlib import Path;"
        "from ibek.pattern_cmds.schema import generate_schema_dict, merge_entities;"
        f"b=generate_schema_dict([Path(r'{support[0]}')]);"
        f"m=merge_entities(b,[Path(r'{support[1]}')]);"
        "print(json.dumps(m, indent=2))"
    )
    outputs = []
    for seed in ("0", "1", "42"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, env=env
        )
        assert result.returncode == 0, result.stderr
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1] == outputs[2]


# --------------------------------------------------------------------------- #
# instance schema generation
# --------------------------------------------------------------------------- #
def test_generate_instance_schema_merges_and_rewrites_header(
    tmp_path: Path, library: Path, samples: Path, monkeypatch
):
    instance = make_instance(
        tmp_path, image="ghcr.io/epics-containers/ioc-adsimdetector-runtime:2025.11.1"
    )
    monkeypatch.setenv("IBEK_SCHEMA_CACHE", str(tmp_path / "cache"))
    # base schema served for the image (built from a real sample module)
    support = sorted((samples / "support").glob("*.ibek.support.yaml"))
    base = generate_schema_dict([support[0]])
    monkeypatch.setattr(schema, "_http_get", lambda url: json.dumps(base).encode())
    # vendor mydevice so its support yaml is in config/
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))

    assert generate_instance_schema(instance) is True
    schema_file = instance / IOC_SCHEMA_NAME
    assert schema_file.exists()
    produced = json.loads(schema_file.read_text())
    mapping = produced["properties"]["entities"]["items"]["discriminator"]["mapping"]
    assert "mydevice.mydevice" in mapping  # vendored entity merged into base
    # ioc.yaml header rewritten to the sibling schema
    header = (instance / "config" / "ioc.yaml").read_text().splitlines()[0]
    assert header == f"# yaml-language-server: $schema=../{IOC_SCHEMA_NAME}"


def test_generate_instance_schema_no_image_is_graceful(tmp_path: Path, capsys):
    instance = make_instance(tmp_path, image="REPLACE_WITH_IMAGE_URI")
    assert generate_instance_schema(instance) is False
    assert not (instance / IOC_SCHEMA_NAME).exists()
    assert "Schema not found" in capsys.readouterr().out


def test_generate_instance_schema_fetch_failure_is_graceful(
    tmp_path: Path, monkeypatch, capsys
):
    instance = make_instance(
        tmp_path, image="ghcr.io/epics-containers/ioc-missing-runtime:9.9.9"
    )
    monkeypatch.setenv("IBEK_SCHEMA_CACHE", str(tmp_path / "cache"))

    def boom(url):
        raise schema.SchemaNotFoundError("404")

    monkeypatch.setattr(schema, "_http_get", boom)
    assert generate_instance_schema(instance) is False
    assert "Schema not found" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# CLI integration
# --------------------------------------------------------------------------- #
def test_cli_add_and_check(tmp_path: Path, library: Path):
    instance = make_instance(tmp_path)
    add = runner.invoke(
        cli,
        ["pattern", "add", "mydevice@1.0.0", str(instance), "--source", str(library)],
    )
    assert add.exit_code == 0, add.output
    check = runner.invoke(cli, ["pattern", "check", str(instance)])
    assert check.exit_code == 0, check.output


def test_cli_check_fails_on_drift(tmp_path: Path, library: Path):
    instance = make_instance(tmp_path)
    runner.invoke(
        cli,
        ["pattern", "add", "mydevice@1.0.0", str(instance), "--source", str(library)],
    )
    proto = instance / "config" / "mydevice.proto"
    proto.write_text("tampered\n")
    result = runner.invoke(cli, ["pattern", "check", str(instance)])
    assert result.exit_code == 1
    assert "mismatch" in result.output


def test_cli_check_allow_dirty_env(tmp_path: Path, library: Path, monkeypatch):
    instance = make_instance(tmp_path)
    runner.invoke(
        cli,
        ["pattern", "add", "mydevice@1.0.0", str(instance), "--source", str(library)],
    )
    (instance / "config" / "mydevice.proto").write_text("tampered\n")
    monkeypatch.setenv("IBEK_ALLOW_DIRTY", "1")
    result = runner.invoke(cli, ["pattern", "check", str(instance)])
    assert result.exit_code == 0, result.output
