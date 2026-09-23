"""
Tests for the ``ibek pattern`` runtime-support vendoring subsystem.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ibek.__main__ import cli
from ibek.globals import IOC_SCHEMA_NAME, RUNTIME_LOCK_NAME
from ibek.pattern_cmds import schema, vendor
from ibek.pattern_cmds.lock import LOCK_VERSION, RuntimeLock, file_hash
from ibek.pattern_cmds.manifest import (
    DEFAULT_MANIFEST_YAML,
    MANIFEST_NAME,
    ManifestError,
    load_manifest,
    plan_vendor,
)
from ibek.pattern_cmds.schema import (
    find_image,
    generate_instance_schema,
    generate_schema_dict,
    merge_entities,
    resolve_image_ref,
)
from ibek.pattern_cmds.sources import PatternError, parse_ref

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


def make_instance(
    root: Path, image: str = "REPLACE_WITH_IMAGE_URI", compose: bool = False
) -> Path:
    """Create a minimal IOC instance folder.

    Helm instances pin the image in ``values.yaml``; compose instances pin it in
    ``compose.yml`` (``compose=True``).
    """
    instance = root / "bl01t-ea-test-01"
    (instance / "config").mkdir(parents=True)
    if compose:
        (instance / "compose.yml").write_text(
            f"services:\n  bl01t-ea-test-01:\n    image: {image}\n"
        )
    else:
        (instance / "values.yaml").write_text(f"ioc-instance:\n  image: {image}\n")
    (instance / "config" / "ioc.yaml").write_text(
        "# yaml-language-server: $schema=/epics/ibek-defs/ioc.schema.json\n"
        "ioc_name: test\nentities: []\n"
    )
    return instance


@pytest.fixture
def pattern_library(samples: Path, tmp_path: Path) -> Path:
    """A mutable copy of the committed sample pattern library.

    Copied with ``symlinks=True`` so a staged tree is a faithful reproduction of
    the library (a dereferenced symlink would make the refusal tests vacuous).
    """
    staged = tmp_path / "patterns"
    shutil.copytree(samples / "patterns", staged, symlinks=True)
    return staged


def make_pattern(
    root: Path,
    name: str,
    files: dict[str, str],
    manifest: str | None = None,
) -> Path:
    """Create a one-pattern local library at ``root``; return the library path."""
    pattern = root / name
    for rel, text in files.items():
        target = pattern / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    if manifest is not None:
        (pattern / MANIFEST_NAME).write_text(manifest)
    return root


def tree(root: Path) -> set[str]:
    """Every file below ``root``, as destination-root-relative posix keys."""
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() or p.is_symlink()
    }


# --------------------------------------------------------------------------- #
# add / lock
# --------------------------------------------------------------------------- #
def test_add_vendors_files_and_lock(tmp_path: Path, library: Path):
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))

    proto = instance / "config" / "mydevice.proto"
    support = instance / "config" / "mydevice.ibek.support.yaml"
    assert proto.exists() and support.exists()
    # real files, not symlinks
    assert not proto.is_symlink()
    # byte-identical to the library: no header, no transformation
    assert proto.read_bytes() == (library / "mydevice" / "mydevice.proto").read_bytes()
    assert not proto.read_text().startswith("# Vendored from ")
    assert "getX" in proto.read_text()

    lock = RuntimeLock(instance / RUNTIME_LOCK_NAME)
    assert set(lock.patterns) == {"mydevice"}
    entry = lock.patterns["mydevice"]
    assert entry.version == "1.0.0"
    assert "ibek-runtime-streamdevice" not in entry.source  # local source label
    # lock keys are destination-root-relative, and hash the pristine bytes
    assert entry.files["config/mydevice.proto"] == file_hash(proto.read_bytes())
    assert set(entry.files) == {
        "config/mydevice.proto",
        "config/mydevice.ibek.support.yaml",
    }


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
    lock.patterns["mydevice"].files["config/mydevice.proto"] = (
        "DIRTY # JIRA-123 relay fix"
    )
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
    files = lock.patterns["mydevice"].files
    assert "config/db/extra.db" not in files  # gone from the lock
    assert set(files) == {
        "config/mydevice.proto",
        "config/mydevice.ibek.support.yaml",
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


@pytest.mark.parametrize("operation", [vendor.update, vendor.restore])
def test_revendor_reconstructs_scheme_for_github_lock_label(
    tmp_path: Path, library: Path, mocker, operation
):
    """update *and* restore must resolve a scheme-stripped lock label to https.

    The lock records ``source`` via ``source_label`` (scheme stripped), so a
    github source is stored as ``github.com/org/repo``. Re-vendoring with no
    explicit --source must hand ``git clone`` a real ``https://`` URL, not the
    bare label (which git would treat as a non-existent local path). Both verbs
    share ``_do_vendor``, so both are exercised here — the original bug was that
    only restore normalised the label while update cloned it raw.
    """
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))
    # rewrite the lock to look as if it had been vendored from github
    lock = RuntimeLock(instance / RUNTIME_LOCK_NAME)
    lock.patterns[
        "mydevice"
    ].source = "github.com/epics-containers/ibek-runtime-streamdevice"
    lock.save()

    # capture the URI handed to the fetcher; serve files from the local lib
    captured: dict[str, str] = {}

    def fake_fetch(uri: str, name: str, version, dest: Path) -> Path:
        captured["uri"] = uri
        return library / name

    mocker.patch.object(vendor, "fetch_pattern", side_effect=fake_fetch)

    operation("mydevice", instance)
    assert captured["uri"] == (
        "https://github.com/epics-containers/ibek-runtime-streamdevice"
    )


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
def serve(body: bytes):
    """A fake ``schema._http_get`` that always returns ``body``."""
    return lambda url, headers: schema.Fetched(body, {})


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
    monkeypatch.setattr(schema, "_http_get", serve(json.dumps(base).encode()))
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


def test_find_image_reads_compose_yml(tmp_path: Path):
    image = "ghcr.io/epics-containers/ioc-adsimdetector-runtime:2.11ec3"
    instance = make_instance(tmp_path, image=image, compose=True)
    assert not (instance / "values.yaml").exists()
    assert find_image(instance) == image


def test_generate_instance_schema_compose_merges_and_rewrites_header(
    tmp_path: Path, library: Path, samples: Path, monkeypatch
):
    instance = make_instance(
        tmp_path,
        image="ghcr.io/epics-containers/ioc-adsimdetector-runtime:2025.11.1",
        compose=True,
    )
    monkeypatch.setenv("IBEK_SCHEMA_CACHE", str(tmp_path / "cache"))
    support = sorted((samples / "support").glob("*.ibek.support.yaml"))
    base = generate_schema_dict([support[0]])
    monkeypatch.setattr(schema, "_http_get", serve(json.dumps(base).encode()))
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))

    assert generate_instance_schema(instance) is True
    schema_file = instance / IOC_SCHEMA_NAME
    assert schema_file.exists()
    produced = json.loads(schema_file.read_text())
    mapping = produced["properties"]["entities"]["items"]["discriminator"]["mapping"]
    assert "mydevice.mydevice" in mapping
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

    def boom(url, headers):
        raise schema.SchemaNotFoundError("404")

    monkeypatch.setattr(schema, "_http_get", boom)
    assert generate_instance_schema(instance) is False
    assert "Schema not found" in capsys.readouterr().out


class FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None):
        self.body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


def test_http_get_uses_system_trust_store(monkeypatch):
    """uv-managed Pythons have no usable OpenSSL CA path on RHEL (#364)."""
    import truststore

    seen = {}

    def fake_urlopen(request, timeout, context):
        seen["context"] = context
        seen["headers"] = dict(request.header_items())
        return FakeResponse(b"{}", {"ETag": '"abc"'})

    monkeypatch.setattr(schema.urllib.request, "urlopen", fake_urlopen)
    fetched = schema._http_get("https://example.com/s.json", {"If-None-Match": "x"})
    assert fetched == schema.Fetched(b"{}", {"ETag": '"abc"'})
    assert isinstance(seen["context"], truststore.SSLContext)
    assert seen["headers"] == {"If-none-match": "x"}


@pytest.mark.parametrize(
    "error, expected",
    [
        (304, None),
        (404, schema.SchemaNotFoundError),
        (410, schema.SchemaNotFoundError),
        (403, schema.SchemaFetchError),
        (408, schema.SchemaFetchError),
        (429, schema.SchemaFetchError),
        (503, schema.SchemaFetchError),
        ("offline", schema.SchemaFetchError),
    ],
)
def test_http_get_classifies_responses(monkeypatch, error, expected):
    import urllib.error

    url = "https://example.com/s.json"

    def fake_urlopen(request, timeout, context):
        if error == "offline":
            raise urllib.error.URLError("Name or service not known")
        raise urllib.error.HTTPError(url, error, "status", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(schema.urllib.request, "urlopen", fake_urlopen)
    if expected is None:
        assert schema._http_get(url, {}) == schema.Fetched(None, {})
    else:
        with pytest.raises(expected) as info:
            schema._http_get(url, {})
        # a missing schema must not be mistaken for an unreachable server
        assert type(info.value) is expected


IMAGE = "ghcr.io/epics-containers/ioc-adsimdetector-runtime:2025.11.1"


class FakeServer:
    """Serve one schema with an ETag, honouring If-None-Match."""

    def __init__(self, schema_dict: dict, etag: str = '"v1"'):
        self.schema = schema_dict
        self.etag = etag
        self.offline = False
        self.requests: list[dict[str, str]] = []

    def __call__(self, url: str, headers: dict[str, str]) -> schema.Fetched:
        self.requests.append(headers)
        if self.offline:
            raise schema.SchemaFetchError("offline")
        if headers.get("If-None-Match") == self.etag:
            return schema.Fetched(None, {})
        body = json.dumps(self.schema).encode()
        return schema.Fetched(body, {"ETag": self.etag})


def test_fetch_base_schema_revalidates_cache(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("IBEK_SCHEMA_CACHE", str(tmp_path / "cache"))
    server = FakeServer({"version": 1})
    monkeypatch.setattr(schema, "_http_get", server)

    assert schema.fetch_base_schema(IMAGE) == {"version": 1}
    assert server.requests[-1] == {}

    # unchanged asset: conditional request, 304, cached copy used
    assert schema.fetch_base_schema(IMAGE) == {"version": 1}
    assert server.requests[-1] == {"If-None-Match": '"v1"'}

    # re-uploaded asset for the same tag reaches the cache
    server.schema, server.etag = {"version": 2}, '"v2"'
    assert schema.fetch_base_schema(IMAGE) == {"version": 2}
    assert "changed since it was cached" in capsys.readouterr().out
    server.offline = True
    assert schema.fetch_base_schema(IMAGE) == {"version": 2}


def test_fetch_base_schema_uses_cache_when_offline(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("IBEK_SCHEMA_CACHE", str(tmp_path / "cache"))
    server = FakeServer({"version": 1})
    monkeypatch.setattr(schema, "_http_get", server)
    schema.fetch_base_schema(IMAGE)

    server.offline = True
    assert schema.fetch_base_schema(IMAGE) == {"version": 1}
    assert "Using cached schema" in capsys.readouterr().out


def test_fetch_base_schema_without_validators_refetches(tmp_path: Path, monkeypatch):
    """A cache written by an older ibek has no validators file."""
    monkeypatch.setenv("IBEK_SCHEMA_CACHE", str(tmp_path / "cache"))
    cache = schema._cache_path(IMAGE)
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"version": "old"}))
    server = FakeServer({"version": 1})
    monkeypatch.setattr(schema, "_http_get", server)

    assert schema.fetch_base_schema(IMAGE) == {"version": 1}
    assert server.requests == [{}]


@pytest.mark.parametrize("record", ["schema", "validators"])
def test_fetch_base_schema_recovers_from_invalid_cache(
    tmp_path: Path, monkeypatch, record
):
    """A partial or corrupt cache record must lead to a fresh download."""
    monkeypatch.setenv("IBEK_SCHEMA_CACHE", str(tmp_path / "cache"))
    server = FakeServer({"version": 1})
    monkeypatch.setattr(schema, "_http_get", server)
    schema.fetch_base_schema(IMAGE)
    cache = schema._cache_path(IMAGE)
    broken = cache if record == "schema" else cache.with_suffix(".validators.json")
    broken.write_text('{"trunc')

    assert schema.fetch_base_schema(IMAGE) == {"version": 1}
    assert server.requests[-1] == {}
    assert json.loads(cache.read_text()) == {"version": 1}
    assert not list(cache.parent.glob(".*"))  # no temporary files left behind


def test_generate_instance_schema_unreachable_without_schema_skips(
    tmp_path: Path, monkeypatch, capsys
):
    instance = make_instance(tmp_path, image=IMAGE)
    monkeypatch.setenv("IBEK_SCHEMA_CACHE", str(tmp_path / "cache"))
    server = FakeServer({})
    server.offline = True
    monkeypatch.setattr(schema, "_http_get", server)

    assert generate_instance_schema(instance) is False
    assert "Schema not found" in capsys.readouterr().out


def test_generate_instance_schema_unreachable_with_schema_fails(
    tmp_path: Path, monkeypatch
):
    """An image bump must not leave the old image's schema in place silently."""
    instance = make_instance(tmp_path, image=IMAGE)
    monkeypatch.setenv("IBEK_SCHEMA_CACHE", str(tmp_path / "cache"))
    (instance / IOC_SCHEMA_NAME).write_text("{}\n")
    server = FakeServer({})
    server.offline = True
    monkeypatch.setattr(schema, "_http_get", server)

    with pytest.raises(schema.StaleSchemaError):
        generate_instance_schema(instance)
    result = runner.invoke(cli, ["pattern", "schema", str(instance)])
    assert result.exit_code == 1
    assert (instance / IOC_SCHEMA_NAME).read_text() == "{}\n"


def test_generate_instance_schema_not_published_with_schema_skips(
    tmp_path: Path, monkeypatch, capsys
):
    instance = make_instance(tmp_path, image=IMAGE)
    monkeypatch.setenv("IBEK_SCHEMA_CACHE", str(tmp_path / "cache"))
    (instance / IOC_SCHEMA_NAME).write_text("{}\n")

    def not_found(url, headers):
        raise schema.SchemaNotFoundError("HTTP Error 404: Not Found")

    monkeypatch.setattr(schema, "_http_get", not_found)
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


def test_cli_schema_says_why_it_did_nothing(tmp_path: Path):
    """`add` is silent about a non-instance destination; `schema` must not be.

    Asking for a schema and getting no output at all is indistinguishable from
    success — here from a `values.yml` typo that no longer pins anything.
    """
    dest = tmp_path / "not-an-instance"
    (dest / "config").mkdir(parents=True)
    (dest / "values.yml").write_text("ioc-instance:\n  image: example.com/x:1\n")

    result = runner.invoke(cli, ["pattern", "schema", str(dest)])
    assert result.exit_code == 0, result.output
    assert "not an IOC instance" in result.output
    assert not (dest / IOC_SCHEMA_NAME).exists()


# --------------------------------------------------------------------------- #
# ibek.manifest.yaml — parsing, validation and the synthesised default
# --------------------------------------------------------------------------- #
def test_load_manifest_synthesises_the_default(pattern_library: Path):
    """No manifest is the *same* code path as an explicit default manifest."""
    pattern = pattern_library / "mydevice"
    assert not (pattern / MANIFEST_NAME).exists()
    synthesised = load_manifest(pattern)
    assert synthesised.version == 1
    assert [(rule.src, rule.dest) for rule in synthesised.vendor] == [(".*", "config")]

    (pattern / MANIFEST_NAME).write_text(DEFAULT_MANIFEST_YAML)
    assert load_manifest(pattern) == synthesised


def test_default_manifest_plan_preserves_nesting(pattern_library: Path):
    pattern = pattern_library / "mydevice"
    implicit = plan_vendor(pattern)
    # an explicit copy of the default must produce an identical plan, and the
    # manifest itself must not appear in it even though ``.*`` matches it
    (pattern / MANIFEST_NAME).write_text(DEFAULT_MANIFEST_YAML)
    explicit = plan_vendor(pattern)
    assert implicit == explicit
    assert [key for _, key in implicit] == [
        "config/db/extra.db",
        "config/mydevice.ibek.support.yaml",
        "config/mydevice.proto",
        "config/mydevice.settings.json",
    ]


def test_add_default_manifest_vendors_everything(tmp_path: Path, pattern_library: Path):
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(pattern_library))

    config = instance / "config"
    assert (config / "db" / "extra.db").exists()  # nesting preserved
    lock = RuntimeLock(instance / RUNTIME_LOCK_NAME)
    assert set(lock.patterns["mydevice"].files) == {
        "config/db/extra.db",
        "config/mydevice.ibek.support.yaml",
        "config/mydevice.proto",
        "config/mydevice.settings.json",
    }
    assert vendor.check(instance).ok


def test_manifest_allow_list_excludes_docs(tmp_path: Path, pattern_library: Path):
    instance = make_instance(tmp_path)
    vendor.add("documented@1.0.0", instance, source_override=str(pattern_library))

    config = instance / "config"
    assert (config / "documented.proto").exists()
    assert (config / "documented.ibek.support.yaml").exists()
    assert not (config / "docs").exists()
    assert not (config / MANIFEST_NAME).exists()

    lock = RuntimeLock(instance / RUNTIME_LOCK_NAME)
    files = lock.patterns["documented"].files
    assert set(files) == {
        "config/documented.proto",
        "config/documented.ibek.support.yaml",
    }
    assert not any("docs" in key for key in files)


def test_manifest_itself_is_never_vendored(tmp_path: Path):
    """Even a manifest that matches itself must not be copied into the dest."""
    library = make_pattern(
        tmp_path / "lib",
        "permissive",
        {"permissive.proto": "body\n"},
        manifest="version: 1\nvendor:\n  - src: '.*'\n    dest: config\n",
    )
    instance = make_instance(tmp_path)
    vendor.add("permissive@1.0.0", instance, source_override=str(library))
    assert not (instance / "config" / MANIFEST_NAME).exists()
    lock = RuntimeLock(instance / RUNTIME_LOCK_NAME)
    assert set(lock.patterns["permissive"].files) == {"config/permissive.proto"}


@pytest.mark.parametrize(
    "manifest, fragment",
    [
        ("version: 99\nvendor:\n  - src: '.*'\n    dest: config\n", "99"),
        (
            "version: 1\nrequires: [other]\nvendor:\n  - src: '.*'\n    dest: config\n",
            "requires",
        ),
        ("version: 1\nvendor: []\n", "vendor"),
        (
            "version: 1\nvendor:\n  - src: '('\n    dest: config\n",
            "src regex",
        ),
        (
            "version: 1\nvendor:\n  - src: '.*'\n    dest: config\n    mode: copy\n",
            "mode",
        ),
    ],
)
def test_manifest_validation_rejects(tmp_path: Path, manifest: str, fragment: str):
    library = make_pattern(
        tmp_path / "lib", "bad", {"bad.proto": "x\n"}, manifest=manifest
    )
    with pytest.raises(ManifestError) as exc:
        load_manifest(library / "bad")
    assert fragment in str(exc.value)
    assert MANIFEST_NAME in str(exc.value)


@pytest.mark.parametrize(
    "rules, expected",
    [
        ([(".*", "config"), (r".*\.proto", "config/protos")], "config/a.proto"),
        ([(r".*\.proto", "config/protos"), (".*", "config")], "config/protos/a.proto"),
    ],
)
def test_manifest_is_ordered_first_match_wins(tmp_path: Path, rules, expected):
    manifest = "version: 1\nvendor:\n" + "".join(
        f"  - src: '{src}'\n    dest: {dest}\n" for src, dest in rules
    )
    library = make_pattern(
        tmp_path / "lib", "ordered", {"a.proto": "x\n"}, manifest=manifest
    )
    assert [key for _, key in plan_vendor(library / "ordered")] == [expected]


def test_manifest_src_is_fullmatch_not_search(tmp_path: Path):
    """``src: config`` must not match ``myconfig/x.template``."""
    library = make_pattern(
        tmp_path / "lib",
        "strict",
        {"myconfig/x.template": "x\n", "config": "y\n"},
        manifest="version: 1\nvendor:\n  - src: 'config'\n    dest: config\n",
    )
    assert [key for _, key in plan_vendor(library / "strict")] == ["config/config"]


# --------------------------------------------------------------------------- #
# round trip for a manifest pattern with an excluded docs/ folder
# --------------------------------------------------------------------------- #
def test_documented_round_trip(tmp_path: Path, pattern_library: Path):
    instance = make_instance(tmp_path)
    docs = instance / "config" / "docs"

    vendor.add("documented@1.0.0", instance, source_override=str(pattern_library))
    assert vendor.check(instance).ok
    assert not docs.exists()

    proto = instance / "config" / "documented.proto"
    proto.write_text(proto.read_text() + "# local hack\n")
    result = vendor.check(instance)
    assert not result.ok
    assert any(
        "config/documented.proto" in f and "mismatch" in f for f in result.failures
    )
    assert not docs.exists()

    vendor.restore("documented", instance)
    assert vendor.check(instance).ok
    assert "# local hack" not in proto.read_text()
    assert not docs.exists()


def test_cli_documented_round_trip(tmp_path: Path, pattern_library: Path):
    instance = make_instance(tmp_path)
    source = ["--source", str(pattern_library)]
    add = runner.invoke(
        cli, ["pattern", "add", "documented@1.0.0", str(instance), *source]
    )
    assert add.exit_code == 0, add.output
    assert runner.invoke(cli, ["pattern", "check", str(instance)]).exit_code == 0

    proto = instance / "config" / "documented.proto"
    proto.write_text("tampered\n")
    assert runner.invoke(cli, ["pattern", "check", str(instance)]).exit_code == 1

    restore = runner.invoke(cli, ["pattern", "restore", str(instance)])
    assert restore.exit_code == 0, restore.output
    assert runner.invoke(cli, ["pattern", "check", str(instance)]).exit_code == 0
    assert not (instance / "config" / "docs").exists()


# --------------------------------------------------------------------------- #
# update across a version that GAINS a manifest
# --------------------------------------------------------------------------- #
V2_MANIFEST = """\
version: 1
vendor:
  - src: '(?:.*/)?(.*\\.db)'
    dest: 'config/\\1'
  - src: '.*\\.(proto|ibek\\.support\\.yaml|settings\\.json)'
    dest: config
"""


def test_update_when_pattern_gains_a_manifest(tmp_path: Path, pattern_library: Path):
    """Orphans resolve against the OLD lock keys, new files against the new plan."""
    pattern = pattern_library / "mydevice"
    (pattern / "docs").mkdir()
    (pattern / "docs" / "README.md").write_text("repo context\n")
    instance = make_instance(tmp_path)

    vendor.add("mydevice@1.0.0", instance, source_override=str(pattern_library))
    config = instance / "config"
    assert (config / "docs" / "README.md").exists()
    assert (config / "db" / "extra.db").exists()

    # v2 gains a manifest: docs are dropped and the db file is re-rooted
    (pattern / MANIFEST_NAME).write_text(V2_MANIFEST)
    vendor.update(
        "mydevice", instance, version="2.0.0", source_override=str(pattern_library)
    )

    assert not (config / "docs" / "README.md").exists()
    assert not (config / "docs").exists()  # newly-empty parent pruned
    assert not (config / "db").exists()  # re-rooted away, parent pruned
    assert (config / "extra.db").exists()  # new destination written

    lock = RuntimeLock(instance / RUNTIME_LOCK_NAME)
    files = lock.patterns["mydevice"].files
    assert set(files) == {
        "config/extra.db",
        "config/mydevice.ibek.support.yaml",
        "config/mydevice.proto",
        "config/mydevice.settings.json",
    }
    assert lock.patterns["mydevice"].version == "2.0.0"
    assert vendor.check(instance).ok


def test_add_over_an_existing_pattern_prunes_orphans(
    tmp_path: Path, pattern_library: Path
):
    """``add`` of a newer version that drops files must not leave them behind."""
    pattern = pattern_library / "mydevice"
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(pattern_library))
    assert (instance / "config" / "db" / "extra.db").exists()

    (pattern / MANIFEST_NAME).write_text(V2_MANIFEST)
    vendor.add("mydevice@2.0.0", instance, source_override=str(pattern_library))

    assert not (instance / "config" / "db").exists()
    assert (instance / "config" / "extra.db").exists()
    assert vendor.check(instance).ok


def test_update_to_a_matchless_manifest_leaves_the_instance_intact(
    tmp_path: Path, pattern_library: Path
):
    """A manifest that matches nothing must not quietly empty the destination.

    Left unchecked this prunes every vendored file, records ``files: {}`` and
    then passes ``check`` having verified nothing — success, in a CI log.
    """
    pattern = pattern_library / "mydevice"
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(pattern_library))
    before = tree(instance)
    lock_before = (instance / RUNTIME_LOCK_NAME).read_text()

    # a one-character slip: `.proto` never fullmatches `mydevice.proto`'s
    # neighbours, and `.protocol` is not what this pattern ships
    (pattern / MANIFEST_NAME).write_text(
        "version: 1\nvendor:\n  - src: '.*\\.protocol'\n    dest: config\n"
    )
    with pytest.raises(PatternError) as exc:
        vendor.update(
            "mydevice", instance, version="2.0.0", source_override=str(pattern_library)
        )
    assert "nothing would be vendored" in str(exc.value)

    assert tree(instance) == before
    assert (instance / RUNTIME_LOCK_NAME).read_text() == lock_before
    assert vendor.check(instance).ok


def test_update_refuses_when_a_vendored_file_blocks_a_new_folder(
    tmp_path: Path, library: Path
):
    """Upstream turning a file into a folder must not half-write the destination.

    ``config/notes`` cannot be a file and the folder holding ``config/notes/x``,
    and finding that out mid-write leaves files on disk with no lock covering
    them.
    """
    pattern = library / "mydevice"
    (pattern / "notes").write_text("v1 was a file\n")
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))
    before = tree(instance)

    (pattern / "notes").unlink()
    (pattern / "notes").mkdir()
    (pattern / "notes" / "x.md").write_text("v2 is a folder\n")
    with pytest.raises(PatternError) as exc:
        vendor.update(
            "mydevice", instance, version="2.0.0", source_override=str(library)
        )
    assert "not a directory" in str(exc.value)

    assert tree(instance) == before
    assert vendor.check(instance).ok


# --------------------------------------------------------------------------- #
# rejection tests — every failure names the offender and writes nothing
# --------------------------------------------------------------------------- #
def assert_add_rejected(
    library: Path, ref: str, instance: Path, *fragments: str
) -> str:
    """Vendoring must abort with a naming error and leave the dest untouched."""
    before = tree(instance)
    with pytest.raises(PatternError) as exc:
        vendor.add(ref, instance, source_override=str(library))
    message = str(exc.value)
    for fragment in fragments:
        assert fragment in message, message
    # validation-before-write: not a single file reached the destination
    assert tree(instance) == before
    return message


def test_reject_absolute_dest(tmp_path: Path):
    library = make_pattern(
        tmp_path / "lib",
        "abs",
        {"abs.proto": "x\n"},
        manifest="version: 1\nvendor:\n  - src: '.*'\n    dest: /etc/config\n",
    )
    assert_add_rejected(
        library, "abs@1.0.0", make_instance(tmp_path), "/etc/config", "relative"
    )


def test_reject_dotdot_in_plain_dest(tmp_path: Path):
    library = make_pattern(
        tmp_path / "lib",
        "escape",
        {"escape.proto": "x\n"},
        manifest="version: 1\nvendor:\n  - src: '.*'\n    dest: ../escape\n",
    )
    assert_add_rejected(
        library, "escape@1.0.0", make_instance(tmp_path), "../escape", ".."
    )


def test_reject_dotdot_introduced_by_a_substitution(tmp_path: Path):
    """A capture group can smuggle in a ``..`` that the template never contains."""
    library = make_pattern(
        tmp_path / "lib",
        "subst",
        {"x/..y/z.proto": "x\n"},
        manifest=(
            "version: 1\nvendor:\n  - src: '(.*)y/(.*)'\n    dest: 'config/\\1/\\2'\n"
        ),
    )
    assert_add_rejected(
        library,
        "subst@1.0.0",
        make_instance(tmp_path),
        "x/..y/z.proto",
        "config/x/../z.proto",
    )


def test_reject_symlink_in_pattern_folder(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("SUPER-SECRET\n")
    library = make_pattern(tmp_path / "lib", "linky", {"linky.proto": "ok\n"})
    try:
        os.symlink(outside / "secret.txt", library / "linky" / "linky.template")
        os.symlink(outside, library / "linky" / "extra", target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - POSIX in CI
        pytest.skip("symlink creation unavailable on this platform")

    instance = make_instance(tmp_path)
    assert_add_rejected(library, "linky@1.0.0", instance, "symlink", "extra")
    # the symlink target's content is nowhere in the destination
    for path in instance.rglob("*"):
        if path.is_file():
            assert "SUPER-SECRET" not in path.read_text()


def test_reject_symlinked_pattern_folder(tmp_path: Path):
    """The refusal must cover the pattern folder itself, not just its contents.

    ``rglob`` never yields the folder, and both ``is_dir()`` and ``copytree``
    dereference it — so the link is erased before the walk ever runs and the
    target's files arrive looking like ordinary pattern files.
    """
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "id_rsa").write_text("SUPER-SECRET-PRIVATE-KEY\n")
    library = tmp_path / "lib"
    library.mkdir()
    try:
        os.symlink(secrets, library / "evil", target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - POSIX in CI
        pytest.skip("symlink creation unavailable on this platform")

    instance = make_instance(tmp_path)
    assert_add_rejected(library, "evil@1.0.0", instance, "symlink", "evil")
    for path in instance.rglob("*"):
        if path.is_file():
            assert "SUPER-SECRET" not in path.read_text()


def test_reject_symlinked_manifest(tmp_path: Path):
    """The manifest is a file in the pattern folder like any other.

    Read before the walk, it is the one file whose link *is* followed — and a
    link to a directory then surfaces as a raw ``IsADirectoryError`` traceback
    rather than as a named pattern error.
    """
    library = make_pattern(tmp_path / "lib", "linky", {"linky.proto": "ok\n"})
    try:
        os.symlink(tmp_path, library / "linky" / MANIFEST_NAME)
    except (OSError, NotImplementedError):  # pragma: no cover - POSIX in CI
        pytest.skip("symlink creation unavailable on this platform")

    assert_add_rejected(
        library, "linky@1.0.0", make_instance(tmp_path), "symlink", MANIFEST_NAME
    )
    with pytest.raises(ManifestError):
        load_manifest(library / "linky")


def test_reject_manifest_that_matches_no_file(tmp_path: Path):
    """The same mistake as ``vendor: []``, one character further on."""
    library = make_pattern(
        tmp_path / "lib",
        "gauge",
        {"gauge.protocol": "getP {}\n", "gauge.ibek.support.yaml": "module: gauge\n"},
        # `.proto` does not fullmatch `gauge.protocol`
        manifest="version: 1\nvendor:\n  - src: '.*\\.(proto|template)'\n"
        "    dest: config\n",
    )
    with pytest.raises(ManifestError) as exc:
        plan_vendor(library / "gauge")
    assert "nothing would be vendored" in str(exc.value)
    assert "gauge" in str(exc.value)


def test_reject_future_manifest_version_before_its_future_keys(tmp_path: Path):
    """A future manifest must be reported as a future manifest.

    Unknown keys are forbidden, so a manifest carrying one is rejected for the
    key unless the version is checked first — telling the reader their manifest
    is illegal rather than that their ibek is too old to read it.
    """
    library = make_pattern(
        tmp_path / "lib",
        "future",
        {"future.proto": "x\n"},
        manifest="version: 2\nrequires: [asyn]\nvendor:\n"
        "  - src: '.*'\n    dest: config\n",
    )
    with pytest.raises(ManifestError) as exc:
        load_manifest(library / "future")
    message = str(exc.value)
    assert "version" in message and "2" in message
    assert "upgrade ibek" in message
    assert "requires" not in message


def test_reject_destination_collision_between_key_spellings(tmp_path: Path):
    """``config/./x.proto`` and ``config/x.proto`` are one file, not two.

    Compared as raw strings they look distinct, so both are planned, both are
    written to the same path, and the lock records two different hashes for the
    one that survives — after which ``check`` fails forever and neither
    ``restore`` nor ``update`` can repair it.
    """
    library = make_pattern(
        tmp_path / "lib",
        "dotslash",
        {"x.proto": "TOP\n", "sub/x.proto": "NESTED\n"},
        manifest=(
            "version: 1\nvendor:\n"
            "  - src: 'sub/(.*)'\n    dest: 'config/\\1'\n"
            "  - src: '(.*)'\n    dest: 'config/./\\1'\n"
        ),
    )
    assert_add_rejected(
        library,
        "dotslash@1.0.0",
        make_instance(tmp_path),
        "config/x.proto",
        "silently overwrite",
    )


def test_reject_destination_that_is_both_a_file_and_a_folder(tmp_path: Path):
    """``config/a`` cannot hold ``config/a/b``; the write finds out too late."""
    library = make_pattern(
        tmp_path / "lib",
        "clash",
        {"a": "FILE-A\n", "sub/b": "FILE-B\n"},
        manifest=(
            "version: 1\nvendor:\n"
            "  - src: 'sub/(.*)'\n    dest: 'config/a/\\1'\n"
            "  - src: '(a)'\n    dest: 'config/\\1'\n"
        ),
    )
    assert_add_rejected(
        library,
        "clash@1.0.0",
        make_instance(tmp_path),
        "config/a/b",
        "config/a",
        "file and a folder",
    )


def test_reject_misrouted_support_yaml(tmp_path: Path):
    library = make_pattern(
        tmp_path / "lib",
        "misrouted",
        {"misrouted.ibek.support.yaml": "module: misrouted\n"},
        manifest="version: 1\nvendor:\n  - src: '.*'\n    dest: config/sub\n",
    )
    assert_add_rejected(
        library,
        "misrouted@1.0.0",
        make_instance(tmp_path),
        "misrouted.ibek.support.yaml",
        "config/sub/misrouted.ibek.support.yaml",
        "config/",
    )


def test_support_yaml_rule_is_conditional_on_being_vendored(tmp_path: Path):
    """The two non-error rows of the placement table."""
    # (1) the pattern ships no support yaml at all
    no_yaml = make_pattern(
        tmp_path / "lib1",
        "noyaml",
        {"noyaml.proto": "x\n"},
        manifest="version: 1\nvendor:\n  - src: '.*'\n    dest: config/sub\n",
    )
    assert [key for _, key in plan_vendor(no_yaml / "noyaml")] == [
        "config/sub/noyaml.proto"
    ]

    # (2) it ships one, but the allow-list does not match it
    unmatched = make_pattern(
        tmp_path / "lib2",
        "unmatched",
        {"unmatched.proto": "x\n", "unmatched.ibek.support.yaml": "module: x\n"},
        manifest="version: 1\nvendor:\n  - src: '.*\\.proto'\n    dest: config/sub\n",
    )
    assert [key for _, key in plan_vendor(unmatched / "unmatched")] == [
        "config/sub/unmatched.proto"
    ]


def test_reject_destination_collision(tmp_path: Path):
    """Two sources flattened onto one key would silently lose a file."""
    library = make_pattern(
        tmp_path / "lib",
        "collide",
        {"a/x.proto": "one\n", "b/x.proto": "two\n"},
        manifest=("version: 1\nvendor:\n  - src: '.*/(.*)'\n    dest: 'config/\\1'\n"),
    )
    assert_add_rejected(
        library, "collide@1.0.0", make_instance(tmp_path), "config/x.proto", "a/x.proto"
    )


# --------------------------------------------------------------------------- #
# byte identity with the library
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", ["mydevice", "documented"])
def test_vendored_bytes_are_identical_to_the_library(
    tmp_path: Path, pattern_library: Path, name: str
):
    instance = make_instance(tmp_path)
    vendor.add(f"{name}@1.0.0", instance, source_override=str(pattern_library))

    plan = {key: src for src, key in plan_vendor(pattern_library / name)}
    assert plan  # the pattern really did vendor something
    entry = RuntimeLock(instance / RUNTIME_LOCK_NAME).patterns[name]
    assert set(entry.files) == set(plan)
    for key, source in plan.items():
        vendored = instance / key
        assert vendored.read_bytes() == source.read_bytes()
        assert entry.files[key] == file_hash(source.read_bytes())
        assert not vendored.read_bytes().startswith(b"# Vendored from")


def test_non_hash_comment_file_is_not_corrupted(tmp_path: Path, pattern_library: Path):
    """A ``.json`` file would not survive a ``#`` header line."""
    instance = make_instance(tmp_path)
    vendor.add("mydevice@1.0.0", instance, source_override=str(pattern_library))
    settings = instance / "config" / "mydevice.settings.json"
    assert json.loads(settings.read_text())["channels"] == [1, 2, 3]


# --------------------------------------------------------------------------- #
# non-instance destinations
# --------------------------------------------------------------------------- #
def test_add_to_bare_destination_is_silent_about_schema(
    tmp_path: Path, pattern_library: Path, capsys
):
    dest = tmp_path / "bare"
    dest.mkdir()
    capsys.readouterr()
    vendor.add("mydevice@1.0.0", dest, source_override=str(pattern_library))

    captured = capsys.readouterr()
    assert "Schema not found" not in captured.out
    assert captured.out.strip() == ""
    assert (dest / "config" / "mydevice.proto").exists()
    assert (dest / RUNTIME_LOCK_NAME).exists()
    assert generate_instance_schema(dest) is False
    assert capsys.readouterr().out.strip() == ""


# --------------------------------------------------------------------------- #
# runtime-lock.yaml root wrapper
# --------------------------------------------------------------------------- #
def test_lock_round_trip_has_root_wrapper(tmp_path: Path):
    path = tmp_path / RUNTIME_LOCK_NAME
    lock = RuntimeLock(path)
    lock.set_pattern("zebra", "1.0.0", "local", {"config/z.proto": "sha256:1"})
    lock.set_pattern("alpha", "2.0.0", "local", {"config/a.proto": "sha256:2"})
    lock.save()

    text = path.read_text()
    assert text.startswith(f"version: {LOCK_VERSION}")
    assert "patterns:" in text
    assert text.index("alpha:") < text.index("zebra:")  # stable diffs

    reloaded = RuntimeLock(path)
    assert list(reloaded.patterns) == ["alpha", "zebra"]
    assert reloaded.patterns["alpha"].files == {"config/a.proto": "sha256:2"}


def write_unwrapped_lock(instance: Path, library: Path, extra_files: str = "") -> Path:
    """Write a lock whose top level is ``{pattern_name: entry}`` directly,
    rather than ``version:`` / ``patterns:`` — a shape this ibek does not
    parse."""
    path = instance / RUNTIME_LOCK_NAME
    path.write_text(
        "mydevice:\n"
        "  version: 1.0.0\n"
        f"  source: {library}\n"
        "  files:\n"
        "    mydevice.proto: sha256:deadbeef\n"
        "    mydevice.ibek.support.yaml: sha256:deadbeef\n" + extra_files
    )
    return path


def test_unrecognised_lock_is_refused(tmp_path: Path, library: Path):
    """A lock whose top level is not ``{version:, patterns:}`` is refused.

    Reading it as an *empty* lock would let ``check`` pass having verified
    nothing, so it must never be silently accepted.
    """
    instance = make_instance(tmp_path)
    path = write_unwrapped_lock(instance, library)

    with pytest.raises(PatternError) as exc:
        RuntimeLock(path)
    assert "scripts/convert-runtime-lock.py" in str(exc.value)


def test_check_refuses_an_unrecognised_lock(tmp_path: Path, library: Path):
    instance = make_instance(tmp_path)
    write_unwrapped_lock(instance, library)

    result = vendor.check(instance)
    assert not result.ok
    assert any(
        "scripts/convert-runtime-lock.py" in failure for failure in result.failures
    )
    assert runner.invoke(cli, ["pattern", "check", str(instance)]).exit_code == 1


def test_add_refuses_an_unrecognised_lock(tmp_path: Path, library: Path):
    instance = make_instance(tmp_path)
    path = write_unwrapped_lock(instance, library)
    before = path.read_text()

    with pytest.raises(PatternError) as exc:
        vendor.add("mydevice@1.0.0", instance, source_override=str(library))
    assert "scripts/convert-runtime-lock.py" in str(exc.value)
    # untouched: nothing was written on top of a lock ibek could not open
    assert path.read_text() == before


def test_update_refuses_an_unrecognised_lock(tmp_path: Path, library: Path):
    instance = make_instance(tmp_path)
    write_unwrapped_lock(instance, library)

    with pytest.raises(PatternError) as exc:
        vendor.update("mydevice", instance, source_override=str(library))
    assert "scripts/convert-runtime-lock.py" in str(exc.value)


def test_unreadable_lock_cannot_be_masked_by_allow_dirty(tmp_path: Path):
    """A lock that verified nothing must not be downgradable to a warning."""
    instance = make_instance(tmp_path)
    (instance / RUNTIME_LOCK_NAME).write_text("- not\n- a mapping\n")

    assert not vendor.check(instance).ok
    assert not vendor.check(instance, allow_dirty=True).ok
    assert runner.invoke(cli, ["pattern", "check", str(instance)]).exit_code == 1


def test_lock_rejects_a_future_version(tmp_path: Path):
    path = tmp_path / RUNTIME_LOCK_NAME
    path.write_text("version: 99\npatterns: {}\n")
    with pytest.raises(PatternError) as exc:
        RuntimeLock(path)
    assert "99" in str(exc.value)


def test_check_does_not_add_a_conversion_hint_to_a_recognised_lock(tmp_path: Path):
    """A missing file under a root-level key is reported plainly.

    A destination-root key with no slash (a ``dest: '\\1'`` manifest root
    placement) is a legitimate lock key in its own right, not a sign the lock
    needs converting.
    """
    library = make_pattern(
        tmp_path / "lib",
        "rooted",
        {"Dockerfile": "FROM scratch\n"},
        manifest="version: 1\nvendor:\n  - src: '(.*)'\n    dest: '\\1'\n",
    )
    instance = make_instance(tmp_path)
    vendor.add("rooted@1.0.0", instance, source_override=str(library))
    assert set(RuntimeLock(instance / RUNTIME_LOCK_NAME).patterns["rooted"].files) == {
        "Dockerfile"
    }

    (instance / "Dockerfile").unlink()
    result = vendor.check(instance)
    assert any("missing vendored file" in f for f in result.failures)
    assert not any("convert" in f for f in result.failures)


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("version: 1\npatterns:\n  bad: 3\n", "invalid pattern entry"),
        ("- not\n- a mapping\n", "mapping"),
        ("version: 1\npatterns: [1, 2]\n", "'patterns' must be a mapping"),
    ],
)
def test_lock_rejects_a_malformed_document(tmp_path: Path, text: str, fragment: str):
    """No lock failure may reach the user as a raw traceback."""
    path = tmp_path / RUNTIME_LOCK_NAME
    path.write_text(text)
    with pytest.raises(PatternError) as exc:
        RuntimeLock(path)
    assert fragment in str(exc.value)


def test_prune_orphans_never_escapes_the_destination(tmp_path: Path, library: Path):
    """Lock keys are free-form strings; a key that climbs out must be refused."""
    instance = make_instance(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("user data\n")
    vendor.add("mydevice@1.0.0", instance, source_override=str(library))

    vendor._prune_orphans(
        instance, {"../outside.txt", "/etc/hosts", "config/mydevice.proto"}
    )
    assert outside.read_text() == "user data\n"
    assert not (instance / "config" / "mydevice.proto").exists()  # in-scope key pruned
