"""
Per-instance ``ioc.schema.json`` generation for IOC instances.

The schema for an instance is *self-contained*: ibek fetches the published base
schema for the instance's pinned image and programmatically merges the instance's
vendored / local support entities into the discriminated ``oneOf`` /
``discriminator.mapping`` / ``$defs``. The same function backs ``ibek pattern``,
pre-commit and CI.

If no published schema can be found for the instance's image, this is reported
and the schema is left untouched (not an error) — generic images that have not
published a schema release simply do not get editor validation.

The base schema URL is derived from the image: a GitHub release asset for an
image on ``ghcr.io`` (or with no registry host), and a GitLab release asset for
an image on any other registry. A ``schema_url`` recorded in the instance's
``runtime-lock.yaml`` replaces the derived URL, and the ``IBEK_SCHEMA_URL``
environment variable replaces both. A GitLab token is sent only to a GitLab
host, over HTTPS.

Downloaded base schemas are cached per image tag and revalidated on every run
with a conditional request, so a re-uploaded release asset reaches the cache.
If the server cannot be reached, the cached copy is used. If there is no cached
copy and the instance already has an ``ioc.schema.json``, generation fails:
that schema may belong to a different image and must not pass silently.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

import truststore
from ruamel.yaml import YAML

from ibek.entity_factory import EntityFactory
from ibek.globals import IOC_SCHEMA_NAME, RUNTIME_LOCK_NAME
from ibek.ioc_factory import IocFactory

from .lock import RuntimeLock
from .sources import PatternError

# Entity defs always present in a generated base schema; never re-copied on merge.
BUILTIN_DEFS = {"RepeatEntity", "Wait4IPEntity", "Wait4USBEntity"}

PUBLISHED_SCHEMA_ASSET = "ibek.ioc.schema.json"
# Only these statuses prove that no schema is published. Other 4xx responses,
# such as 403, 408 or 429, can be transient and must not hide a stale schema.
NOT_PUBLISHED_STATUSES = {404, 410}
SCHEMA_HEADER = f"# yaml-language-server: $schema=../{IOC_SCHEMA_NAME}"


class SchemaNotFoundError(Exception):
    """The published base schema for an image could not be located."""


class SchemaFetchError(SchemaNotFoundError):
    """The schema server could not be reached, so the schema may still exist."""


class StaleSchemaError(PatternError):
    """An instance schema exists but its base schema could not be fetched."""


class Fetched(NamedTuple):
    """An HTTP response: ``body`` is None for 304 Not Modified."""

    body: bytes | None
    validators: dict[str, str]


# --------------------------------------------------------------------------- #
# image ref -> published release asset
# --------------------------------------------------------------------------- #
# Docker Hub is the registry for a ref that names no host.
DEFAULT_REGISTRY = "docker.io"
# Images on these registries (and on none) publish their schema as a GitHub
# release asset; images on any other registry are assumed to be on GitLab.
GITHUB_REGISTRIES = {"ghcr.io", DEFAULT_REGISTRY}
# A one-off override of the schema URL for every instance in this run.
SCHEMA_URL_ENV = "IBEK_SCHEMA_URL"
# The placeholders a schema URL override may contain.
URL_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
# A final -developer/-runtime and its optional architecture infix.
IMAGE_SUFFIX = re.compile(r"(-linux|-rtems-beatnik)?(-developer|-runtime)$")


class ImageRef(NamedTuple):
    """A parsed image ref: ``host`` is None when the ref names no registry."""

    host: str | None
    path: tuple[str, ...]
    tag: str


def parse_image_ref(image: str) -> ImageRef:
    """Split a container image ref into registry host, path parts and tag.

    Follows Docker's reference grammar: the first part is a registry host only
    if it contains ``.`` or ``:`` or is ``localhost``, and the tag is split off
    the last part only, so a registry port is not mistaken for a tag. A
    trailing ``@digest`` is ignored; the schema is keyed on the tag.
    """
    ref = image.strip().partition("@")[0]
    parts = ref.split("/")
    host = None
    if len(parts) > 1 and (
        "." in parts[0] or ":" in parts[0] or parts[0] == "localhost"
    ):
        host = parts.pop(0)
    name, _, tag = parts[-1].partition(":")
    if not tag:
        raise SchemaNotFoundError(f"image {image!r} has no tag")
    path = (*parts[:-1], name)
    if any(part in ("", ".", "..") for part in path):
        raise SchemaNotFoundError(f"cannot parse image path from {image!r}")
    return ImageRef(host, path, tag)


def _base_name(name: str) -> str:
    """Strip the developer/runtime suffix and optional architecture infix."""
    return IMAGE_SUFFIX.sub("", name)


def resolve_image_ref(image: str) -> tuple[str, str, str]:
    """Map a container image ref to ``(org, repo, tag)`` for the GitHub rule.

    ``ghcr.io/epics-containers/ioc-adsimdetector-runtime:2025.11.1`` ->
    ``("epics-containers", "ioc-adsimdetector", "2025.11.1")``.
    """
    ref = parse_image_ref(image)
    if len(ref.path) < 2:
        raise SchemaNotFoundError(f"cannot parse org/repo from image {image!r}")
    return ref.path[0], _base_name(ref.path[-1]), ref.tag


def gitlab_web_host(registry: str) -> str:
    """Map a GitLab container registry host to the GitLab web host.

    Drops any port and a ``registry.`` prefix:
    ``gitlab.diamond.ac.uk:5050`` and ``registry.gitlab.com`` ->
    ``gitlab.diamond.ac.uk`` and ``gitlab.com``.
    """
    host = registry.partition(":")[0]
    return host.removeprefix("registry.")


def published_schema_url(image: str) -> str:
    """Build the release-asset URL of an image's published schema.

    An image on ``ghcr.io``, or with no registry host, maps to a GitHub
    release asset of ``<org>/<repo>``. An image on any other registry maps to
    a GitLab release asset: the GitLab flavour of ioc-template pushes
    ``<registry>/<project path>/<name>-<arch>-<target>:<tag>``, so the
    project is the image path without its last part.
    """
    ref = parse_image_ref(image)
    if ref.host is None or ref.host in GITHUB_REGISTRIES:
        org, repo, tag = resolve_image_ref(image)
        return (
            f"https://github.com/{org}/{repo}/releases/download/{tag}/"
            f"{PUBLISHED_SCHEMA_ASSET}"
        )
    if len(ref.path) < 2:
        raise SchemaNotFoundError(f"cannot parse project path from image {image!r}")
    project = "/".join(ref.path[:-1])
    return (
        f"https://{gitlab_web_host(ref.host)}/{project}/-/releases/{ref.tag}/"
        f"downloads/{PUBLISHED_SCHEMA_ASSET}"
    )


def expand_schema_url(template: str, image: str) -> str:
    """Fill the placeholders of a schema URL override from ``image``.

    ``{registry}`` is the registry host (``docker.io`` when the image names
    none), ``{project}`` the image path without its last part, ``{name}`` the
    last part without its developer/runtime suffix, and ``{tag}`` the tag.
    """
    ref = parse_image_ref(image)
    values = {
        "registry": ref.host or DEFAULT_REGISTRY,
        "project": "/".join(ref.path[:-1]),
        "name": _base_name(ref.path[-1]),
        "tag": ref.tag,
    }

    def fill(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise PatternError(
                f"schema URL {template!r}: unknown placeholder {{{key}}} "
                f"(use {', '.join('{' + k + '}' for k in values)})"
            )
        return values[key]

    return URL_PLACEHOLDER.sub(fill, template)


def schema_url(image: str, recorded: str | None = None) -> str:
    """Return the base-schema URL for ``image``.

    ``IBEK_SCHEMA_URL`` wins, then ``recorded`` (the instance lock's
    ``schema_url``), then the URL derived from the image.
    """
    override = os.getenv(SCHEMA_URL_ENV, "").strip() or recorded
    if override:
        return expand_schema_url(override, image)
    return published_schema_url(image)


def _cache_path(image: str) -> Path:
    """Return the cache file for an image's base schema.

    The key is the registry host, the full image path and the tag, one
    directory per part, so images with the same name on different registries
    cannot collide. The last part has its developer/runtime suffix stripped,
    so the variants of one image share an entry.
    """
    ref = parse_image_ref(image)
    root = Path(
        os.getenv("IBEK_SCHEMA_CACHE", Path.home() / ".cache" / "ibek" / "schemas")
    )
    # A host cannot contain "_", so replacing the port's ":" cannot collide.
    host = (ref.host or DEFAULT_REGISTRY).replace(":", "_")
    *parents, name = ref.path
    return root.joinpath(host, *parents, _base_name(name), f"{ref.tag}.json")


# --------------------------------------------------------------------------- #
# authenticated download
# --------------------------------------------------------------------------- #
# Personal, project or group access token, sent as PRIVATE-TOKEN.
GITLAB_TOKEN_ENV = "GITLAB_TOKEN"
# A GitLab CI job's token, sent as JOB-TOKEN, only to the job's own server.
JOB_TOKEN_ENV = "CI_JOB_TOKEN"
CI_SERVER_HOST_ENV = "CI_SERVER_HOST"
# Hosts that never get a GitLab token, whatever else they match.
GITHUB_HOSTS = ("github.com", "githubusercontent.com", "ghcr.io")
# Where GitLab sends a client that may not see a project without signing in.
GITLAB_SIGN_IN_PATH = "/users/sign_in"


def _is_github_host(host: str) -> bool:
    return any(host == name or host.endswith("." + name) for name in GITHUB_HOSTS)


def _is_gitlab_host(host: str) -> bool:
    """True for a host with a ``gitlab`` label, or this CI job's GitLab server."""
    return "gitlab" in host.split(".") or host == os.getenv(CI_SERVER_HOST_ENV)


def auth_headers(url: str) -> dict[str, str]:
    """Return the token header to send with a request for ``url``.

    A token goes only over HTTPS, only to a GitLab host, and never to a GitHub
    host. ``GITLAB_TOKEN`` is sent as ``PRIVATE-TOKEN``; without it,
    ``CI_JOB_TOKEN`` is sent as ``JOB-TOKEN``, and only to ``CI_SERVER_HOST``,
    the GitLab server that issued it.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or _is_github_host(host):
        return {}
    if not _is_gitlab_host(host):
        return {}
    token = os.getenv(GITLAB_TOKEN_ENV, "").strip()
    if token:
        return {"PRIVATE-TOKEN": token}
    token = os.getenv(JOB_TOKEN_ENV, "").strip()
    if token and host == os.getenv(CI_SERVER_HOST_ENV):
        return {"JOB-TOKEN": token}
    return {}


def _origin(url: str) -> tuple[str, str, int | None]:
    parts = urlsplit(url)
    return parts.scheme, (parts.hostname or "").lower(), parts.port


class _RedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow redirects, sending the token again only to the same origin.

    urllib copies a request's ordinary headers to every redirect, whatever its
    host, so the token travels as an unredirected header and this handler
    re-adds it only when the redirect stays on the scheme, host and port the
    token was meant for. A GitLab release asset redirects to the package API
    on the same host, which needs the token again for a non-public project.
    """

    def __init__(self, url: str, auth: dict[str, str]):
        super().__init__()
        self.origin = _origin(url)
        self.auth = auth

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is None:
            return None
        if urlsplit(newurl).path == GITLAB_SIGN_IN_PATH:
            hint = (
                "the token was refused"
                if self.auth
                else f"set {GITLAB_TOKEN_ENV} to a token with read_api scope"
            )
            raise SchemaFetchError(
                f"could not fetch {req.full_url}: GitLab requires sign-in; {hint}"
            )
        if _origin(newurl) == self.origin:
            for key, value in self.auth.items():
                new.add_unredirected_header(key, value)
        return new


def _opener(
    context: ssl.SSLContext, redirect: urllib.request.HTTPRedirectHandler
) -> urllib.request.OpenerDirector:
    """Build the URL opener (monkeypatched in tests)."""
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context), redirect
    )


def _http_get(url: str, headers: dict[str, str]) -> Fetched:
    """Fetch ``url`` with extra request ``headers`` (monkeypatched in tests).

    Adds the token header that :func:`auth_headers` chooses for ``url``.

    Raises SchemaNotFoundError for a 404 or 410 response, and SchemaFetchError
    for any other failure.
    """
    # Verify against the OS trust store. The uv-managed Python that uvx uses
    # has OpenSSL CA paths compiled for Debian (/etc/ssl/cert.pem), which do
    # not exist on RHEL, so the default context fails verification (#364).
    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    auth = auth_headers(url)
    request = urllib.request.Request(url, headers=headers)
    for key, value in auth.items():
        request.add_unredirected_header(key, value)
    opener = _opener(context, _RedirectHandler(url, auth))
    try:
        with opener.open(request, timeout=10) as response:
            validators = {
                key: response.headers[key]
                for key in ("ETag", "Last-Modified")
                if response.headers.get(key)
            }
            return Fetched(response.read(), validators)
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return Fetched(None, {})
        if exc.code in NOT_PUBLISHED_STATUSES:
            raise SchemaNotFoundError(f"could not fetch {url}: {exc}") from exc
        raise SchemaFetchError(f"could not fetch {url}: {exc}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise SchemaFetchError(f"could not fetch {url}: {exc}") from exc


def _read_json(path: Path) -> dict | None:
    """Return the JSON object in ``path``, or None if it is missing or invalid.

    An interrupted write or a manual edit can leave an invalid cache record,
    which must cause a fresh download rather than a crash.
    """
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_atomic(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` so that readers never see a partial file."""
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as tmp:
        tmp.write(text)
    os.replace(tmp.name, path)


def fetch_base_schema(image: str, recorded_url: str | None = None) -> dict:
    """Return the published base schema for ``image``.

    ``recorded_url`` is the instance's recorded schema URL, if any; see
    :func:`schema_url` for which URL is fetched.

    The cached copy for the image tag is revalidated with ``If-None-Match`` /
    ``If-Modified-Since``. The cached copy is also used when the fetch fails.
    An invalid cache record, or one fetched from another URL, is ignored and
    downloaded again.

    Raises:
        SchemaNotFoundError: no schema is published for the image.
        SchemaFetchError: the fetch failed and nothing is cached.
    """
    url = schema_url(image, recorded_url)
    cache = _cache_path(image)
    validators_path = cache.with_suffix(".validators.json")
    cached = _read_json(cache)

    headers = {}
    validators = _read_json(validators_path) if cached is not None else None
    if validators and validators.get("url", url) != url:
        # The cached schema came from another URL, for example before an
        # override was set, so it is no evidence of what ``url`` serves.
        cached = validators = None
    for key, header in (
        ("ETag", "If-None-Match"),
        ("Last-Modified", "If-Modified-Since"),
    ):
        if validators and isinstance(validators.get(key), str):
            headers[header] = validators[key]

    try:
        fetched = _http_get(url, headers)
    except SchemaFetchError as exc:
        if cached is None:
            raise
        print(f"Using cached schema for {image}, could not revalidate it: {exc}")
        return cached

    if fetched.body is None:
        if cached is None:
            raise SchemaFetchError(f"{url} returned 304 but nothing is cached")
        return cached
    try:
        schema = json.loads(fetched.body)
    except json.JSONDecodeError as exc:
        raise SchemaNotFoundError(f"{url} did not return JSON: {exc}") from exc

    if cached is not None and schema != cached:
        print(f"Published schema for {image} changed since it was cached")
    cache.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(cache, json.dumps(schema, indent=2))
    _write_atomic(validators_path, json.dumps({**fetched.validators, "url": url}))
    return schema


# --------------------------------------------------------------------------- #
# entity merge
# --------------------------------------------------------------------------- #
def generate_schema_dict(support_yamls: list[Path]) -> dict:
    """Generate the ibek IOC JSON schema for exactly ``support_yamls``."""
    entity_factory = EntityFactory()
    entity_models = entity_factory.make_entity_models(list(support_yamls))
    ioc_model = IocFactory().make_ioc_model(entity_models)
    return ioc_model.model_json_schema()


def _union_node(schema: dict) -> dict:
    """Return the discriminated-union node (handles inline and wrapper layouts)."""
    items = schema["properties"]["entities"]["items"]
    if "$ref" in items:
        ref = items["$ref"].split("/")[-1]
        return schema["$defs"][ref]
    return items


def _collect_refs(node: object, acc: set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str) and "/$defs/" in value:
                acc.add(value.split("/")[-1])
            else:
                _collect_refs(value, acc)
    elif isinstance(node, list):
        for item in node:
            _collect_refs(item, acc)


def merge_entities(base: dict, support_yamls: list[Path]) -> dict:
    """Merge the entities defined by ``support_yamls`` into ``base`` in place.

    The extra entities (and the transitive closure of ``$defs`` they reference)
    are grafted into the base schema's ``oneOf`` / ``discriminator.mapping`` /
    ``$defs``. Built-ins and defs already present in the base are not duplicated.
    """
    if not support_yamls:
        return base

    extra = generate_schema_dict(support_yamls)
    base_union = _union_node(base)
    extra_union = _union_node(extra)
    base_defs = base.setdefault("$defs", {})
    extra_defs = extra.get("$defs", {})
    base_mapping = base_union["discriminator"]["mapping"]

    # New top-level entity types: in the extras' mapping, not built-in, not in base.
    new_entities = {
        disc: ref.split("/")[-1]
        for disc, ref in extra_union["discriminator"]["mapping"].items()
        if ref.split("/")[-1] not in BUILTIN_DEFS and disc not in base_mapping
    }

    # Transitive closure of $defs to copy (enums, nested entities, ...).
    needed: set[str] = set(new_entities.values())
    queue = list(needed)
    while queue:
        name = queue.pop()
        definition = extra_defs.get(name)
        if definition is None:
            continue
        refs: set[str] = set()
        _collect_refs(definition, refs)
        for ref in refs:
            if ref in BUILTIN_DEFS or ref in base_defs or ref in needed:
                continue
            needed.add(ref)
            queue.append(ref)

    # Copy and extend in sorted order so the produced schema is byte-stable
    # across runs (set/closure iteration order is otherwise non-deterministic,
    # which would make the CI/pre-commit schema-freshness diff fail spuriously).
    for name in sorted(needed):
        if name in extra_defs and name not in base_defs:
            base_defs[name] = extra_defs[name]

    for disc in sorted(new_entities):
        key = new_entities[disc]
        base_union["oneOf"].append({"$ref": f"#/$defs/{key}"})
        base_mapping[disc] = f"#/$defs/{key}"

    return base


# --------------------------------------------------------------------------- #
# instance schema
# --------------------------------------------------------------------------- #
# Instance image is pinned in ``values.yaml`` (helm) or ``compose.yml`` (compose).
IMAGE_SOURCES = ("values.yaml", "compose.yml", "compose.yaml")


def _image_source(instance_dir: Path) -> Path | None:
    """Return the file an instance pins its image in, if it has one.

    The single definition of "does this folder look like an IOC instance at
    all?" — a destination with neither file is simply not an instance.
    """
    return next(
        (
            instance_dir / name
            for name in IMAGE_SOURCES
            if (instance_dir / name).is_file()
        ),
        None,
    )


def is_instance(instance_dir: Path) -> bool:
    """True if ``instance_dir`` looks like an IOC instance at all.

    Lets a caller that asked for a schema *explicitly* explain why it did
    nothing, while ``add`` / ``update`` stay silent about a destination that was
    never meant to have one.
    """
    return _image_source(instance_dir) is not None


def find_image(instance_dir: Path) -> str | None:
    """Find the IOC image ref in an instance's ``values.yaml`` or ``compose.yml``.

    Helm instances pin the image in ``values.yaml``; compose instances pin it in
    ``compose.yml`` / ``compose.yaml``. The first of these that exists is searched.
    """
    source = _image_source(instance_dir)
    if source is None:
        return None
    data = YAML(typ="safe").load(source) or {}

    found: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "image" and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    for image in found:
        if "/" in image and ":" in image and "REPLACE" not in image.upper():
            return image
    return None


def rewrite_ioc_yaml_header(ioc_yaml: Path) -> None:
    """Set ``ioc.yaml``'s first line to the sibling-schema language-server header."""
    if not ioc_yaml.exists():
        return
    lines = ioc_yaml.read_text().splitlines()
    if lines and lines[0].startswith("# yaml-language-server:"):
        lines[0] = SCHEMA_HEADER
    else:
        lines.insert(0, SCHEMA_HEADER)
    ioc_yaml.write_text("\n".join(lines) + "\n")


def generate_instance_schema(instance_dir: Path) -> bool:
    """Generate ``<instance>/ioc.schema.json`` and rewrite the ``ioc.yaml`` header.

    Returns True if a schema was written, False if the destination is not an IOC
    instance (silent) or the published base schema for the instance's image could
    not be found (reported, not an error).

    Raises:
        StaleSchemaError: the base schema fetch failed with nothing cached, but
            ``ioc.schema.json`` exists and may be for another image.
    """
    config_dir = instance_dir / "config"
    schema_path = instance_dir / IOC_SCHEMA_NAME
    if not is_instance(instance_dir):
        # No values.yaml/compose.yml at all: this destination is not an IOC
        # instance, so there is no schema to generate and nothing to say.
        return False
    image = find_image(instance_dir)
    if image is None:
        print(
            f"Schema not found for {instance_dir.name}: "
            "no published image pinned in values.yaml/compose.yml; "
            "skipping schema generation"
        )
        return False
    recorded_url = RuntimeLock(instance_dir / RUNTIME_LOCK_NAME).schema_url
    try:
        base = fetch_base_schema(image, recorded_url)
    except SchemaNotFoundError as exc:
        if isinstance(exc, SchemaFetchError) and schema_path.exists():
            raise StaleSchemaError(
                f"Cannot refresh {schema_path} (image {image}): {exc}. "
                "The existing schema may be for a different image."
            ) from exc
        print(
            f"Schema not found for {instance_dir.name} (image {image}): {exc}; "
            "skipping schema generation"
        )
        return False

    support_yamls = sorted(config_dir.glob("*.ibek.support.yaml"))
    merged = merge_entities(base, support_yamls)

    schema_path.write_text(json.dumps(merged, indent=2) + "\n")
    rewrite_ioc_yaml_header(config_dir / "ioc.yaml")
    return True
