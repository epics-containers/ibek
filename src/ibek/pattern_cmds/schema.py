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

The base schema is located from the image: a GitHub release asset for an
image on ``ghcr.io`` (or with no registry host), and the ``ibek.ioc.schema.json``
link of a GitLab release, found through the GitLab releases API, for an image
on any other registry. A ``schema_url`` recorded in the instance's
``runtime-lock.yaml`` replaces the derived location, and the ``IBEK_SCHEMA_URL``
environment variable replaces both. A GitLab token is sent only over HTTPS to
a host the operator lists in ``IBEK_GITLAB_HOSTS`` or to ``CI_SERVER_HOST``.

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
from urllib.parse import quote, unquote, urlsplit

import truststore
from ruamel.yaml import YAML

from ibek.entity_factory import EntityFactory
from ibek.globals import IOC_SCHEMA_NAME, RUNTIME_LOCK_NAME
from ibek.ioc_factory import IocFactory

from .lock import RuntimeLock
from .sources import PatternError
from .urls import host_entry_key, origin_key, url_origin_key, url_problem

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


class InvalidSchemaError(PatternError):
    """A fetched base schema does not have the shape of an ibek IOC schema."""


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
# release asset. An image on any other registry is looked up on GitLab, if its
# web host is one the operator lists (see gitlab_hosts).
GITHUB_REGISTRIES = {
    "ghcr.io",
    DEFAULT_REGISTRY,
    "index.docker.io",
    "registry-1.docker.io",
}
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


def _on_github(ref: ImageRef) -> bool:
    return ref.host is None or ref.host in GITHUB_REGISTRIES


def published_schema_url(image: str) -> str:
    """Build the URL that locates an image's published schema.

    An image on ``ghcr.io`` or Docker Hub, or with no registry host, maps to
    the GitHub release asset of ``<org>/<repo>``. An image on a registry whose
    web host is a listed GitLab host maps to the GitLab releases API's list of
    release links, which names the asset (see :func:`_gitlab_asset_url`): the
    GitLab flavour of ioc-template pushes
    ``<registry>/<project path>/<name>-<arch>-<target>:<tag>``, so the
    project is the image path without its last part. Any other registry
    publishes no schema ibek can find.
    """
    ref = parse_image_ref(image)
    if ref.host is None or _on_github(ref):
        org, repo, tag = resolve_image_ref(image)
        return (
            f"https://github.com/{org}/{repo}/releases/download/{tag}/"
            f"{PUBLISHED_SCHEMA_ASSET}"
        )
    web_host = gitlab_web_host(ref.host)
    if origin_key(web_host, None) not in gitlab_hosts():
        raise SchemaNotFoundError(
            f"image {image!r} is on registry {ref.host}, which is neither a "
            f"GitHub or Docker Hub registry nor a GitLab host listed in "
            f"{GITLAB_HOSTS_ENV}; no published schema to look up"
        )
    if len(ref.path) < 2:
        raise SchemaNotFoundError(f"cannot parse project path from image {image!r}")
    project = quote("/".join(ref.path[:-1]), safe="")
    return (
        f"https://{web_host}/api/v4/projects/{project}/"
        f"releases/{quote(ref.tag, safe='')}/assets/links"
    )


def expand_schema_url(template: str, image: str) -> str:
    """Fill the placeholders of a schema URL override from ``image``.

    ``{registry}`` is the registry host (``docker.io`` when the image names
    none), ``{project}`` the image path without its last part,
    ``{project_encoded}`` the same with every ``/`` encoded as ``%2F`` (as the
    GitLab API wants it), ``{name}`` the last part without its
    developer/runtime suffix, and ``{tag}`` the tag.
    """
    ref = parse_image_ref(image)
    project = "/".join(ref.path[:-1])
    values = {
        "registry": ref.host or DEFAULT_REGISTRY,
        "project": project,
        "project_encoded": quote(project, safe=""),
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


def check_schema_url(url: str, origin: str = "schema URL") -> None:
    """Refuse a schema URL override that is not a plain ``https://`` URL.

    Raises PatternError: an override is configuration, so a bad one stops the
    command rather than being skipped.
    """
    problem = url_problem(url)
    if problem:
        raise PatternError(
            f"{origin} {url!r} {problem}; only https:// URLs are allowed"
        )


class SchemaSource(NamedTuple):
    """Where a base schema comes from.

    ``url`` is the schema itself, or, when ``links`` is true, a GitLab
    release's list of links that names it.
    """

    url: str
    links: bool = False


def schema_source(image: str, recorded: str | None = None) -> SchemaSource:
    """Return where to fetch the base schema for ``image``.

    ``IBEK_SCHEMA_URL`` wins, then ``recorded`` (the instance lock's
    ``schema_url``), then the location derived from the image.
    """
    env = os.getenv(SCHEMA_URL_ENV, "").strip()
    override, origin = (env, SCHEMA_URL_ENV) if env else (recorded, "schema_url")
    if override:
        check_schema_url(override, origin)
        url = expand_schema_url(override, image)
        check_schema_url(url, origin)
        return SchemaSource(url)
    url = published_schema_url(image)
    return SchemaSource(url, links=not _on_github(parse_image_ref(image)))


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
# The GitLab hosts that may receive GITLAB_TOKEN, comma-separated. Set by the
# operator, never read from a repository, because image refs and schema URLs
# are repository text that anyone proposing a change can edit.
GITLAB_HOSTS_ENV = "IBEK_GITLAB_HOSTS"
# A GitLab CI job's token, sent as JOB-TOKEN, only to the job's own server.
JOB_TOKEN_ENV = "CI_JOB_TOKEN"
CI_SERVER_HOST_ENV = "CI_SERVER_HOST"
CI_SERVER_PORT_ENV = "CI_SERVER_PORT"
# Hosts that never get a GitLab token, whatever else they match.
GITHUB_HOSTS = ("github.com", "githubusercontent.com", "ghcr.io")
# Where GitLab sends a client that may not see a project without signing in,
# under any relative URL root GitLab is served from.
GITLAB_SIGN_IN_PATH = "/users/sign_in"


def _is_github_host(host: str) -> bool:
    return any(host == name or host.endswith("." + name) for name in GITHUB_HOSTS)


def _ci_server() -> str | None:
    """The :func:`origin_key` of this GitLab CI job's server, if any."""
    host = os.getenv(CI_SERVER_HOST_ENV, "").strip()
    port = os.getenv(CI_SERVER_PORT_ENV, "").strip()
    if not host:
        return None
    return host_entry_key(f"{host}:{port}" if port else host)


def gitlab_hosts() -> set[str]:
    """The GitLab servers ibek looks schemas up on and may send a token to.

    ``IBEK_GITLAB_HOSTS`` (comma-separated ``host[:port]`` entries; a bare
    host means the default HTTPS port) plus this CI job's server, as
    :func:`origin_key` values.
    """
    hosts = {
        key
        for entry in os.getenv(GITLAB_HOSTS_ENV, "").split(",")
        if (key := host_entry_key(entry))
    }
    ci_server = _ci_server()
    if ci_server:
        hosts.add(ci_server)
    return hosts


def auth_headers(url: str) -> dict[str, str]:
    """Return the token header to send with a request for ``url``.

    A token goes only to a plain ``https://`` URL (see :func:`url_problem`)
    whose host and port are in :func:`gitlab_hosts`, and never to a GitHub
    host. ``GITLAB_TOKEN`` is sent as ``PRIVATE-TOKEN``; without it,
    ``CI_JOB_TOKEN`` is sent as ``JOB-TOKEN``, and only to the CI job's own
    server, which issued it.
    """
    if url_problem(url):
        return {}
    host = (urlsplit(url).hostname or "").lower()
    if _is_github_host(host):
        return {}
    key = url_origin_key(url)
    if key not in gitlab_hosts():
        return {}
    token = os.getenv(GITLAB_TOKEN_ENV, "").strip()
    if token:
        return {"PRIVATE-TOKEN": token}
    token = os.getenv(JOB_TOKEN_ENV, "").strip()
    if token and key == _ci_server():
        return {"JOB-TOKEN": token}
    return {}


def _no_token_hint(url: str) -> str:
    """Explain why GitLab may hide a project from a client without a token."""
    host = urlsplit(url).hostname or url
    return (
        "the project may be private or may not exist; to read a private "
        f"project, add {host} to {GITLAB_HOSTS_ENV} and set {GITLAB_TOKEN_ENV}"
    )


REFUSED_HINT = "the token was refused, or the project does not exist"


def _origin(url: str) -> tuple[str, str]:
    """Scheme and :func:`origin_key`: two URLs on one origin share these."""
    return urlsplit(url).scheme.lower(), url_origin_key(url)


class _RedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow redirects, sending the token again only to the same origin.

    urllib copies a request's ordinary headers to every redirect, whatever its
    host, so the token travels as an unredirected header and this handler
    re-adds it only while every redirect so far has stayed on the scheme, host
    and port the token was meant for. A GitLab release asset redirects to the package API
    on the same host, which needs the token again for a non-public project.
    """

    def __init__(self, url: str, auth: dict[str, str]):
        super().__init__()
        self.origin = _origin(url)
        self.auth = auth
        # Set once a redirect leaves the origin: a later hop back to it may
        # be chosen by the other server, so it gets no token either.
        self.left_origin = False

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        problem = url_problem(newurl)
        if problem:
            raise SchemaFetchError(
                f"could not fetch {req.full_url}: refusing a redirect to "
                f"{newurl!r}, which {problem}"
            )
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is None:
            return None
        if urlsplit(newurl).path.endswith(GITLAB_SIGN_IN_PATH):
            # GitLab sends a client here for a project it may not see, which
            # is also how it answers for a project that does not exist.
            message = f"could not fetch {req.full_url}: GitLab requires sign-in"
            if self.auth:
                raise SchemaFetchError(f"{message}; {REFUSED_HINT}")
            raise SchemaNotFoundError(f"{message}; {_no_token_hint(req.full_url)}")
        if _origin(newurl) != self.origin:
            self.left_origin = True
        if not self.left_origin:
            for key, value in self.auth.items():
                new.add_unredirected_header(key, value)
        return new


def _opener(
    context: ssl.SSLContext, redirect: urllib.request.HTTPRedirectHandler
) -> urllib.request.OpenerDirector:
    """Build an HTTPS-only URL opener (monkeypatched in tests).

    ``build_opener`` would add handlers for ``file:``, ``ftp:``, ``data:`` and
    plain ``http:`` URLs; a schema URL is repository text, so none of them is
    installed and such a URL fails as an unknown URL type. The proxy handler
    honours ``HTTPS_PROXY`` and ``NO_PROXY``, and is given only the ``https``
    proxy, so no other proxy setting can add a handler for another scheme.
    """
    proxies = urllib.request.getproxies()
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler(
            {"https": proxies["https"]} if "https" in proxies else {}
        ),
        urllib.request.UnknownHandler(),
        urllib.request.HTTPSHandler(context=context),
        urllib.request.HTTPDefaultErrorHandler(),
        redirect,
        urllib.request.HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener


def _http_get(url: str, headers: dict[str, str], anonymous: bool = False) -> Fetched:
    """Fetch ``url`` with extra request ``headers`` (monkeypatched in tests).

    Adds the token header that :func:`auth_headers` chooses for ``url``,
    unless ``anonymous``. Refuses any URL :func:`url_problem` rejects.

    Raises SchemaNotFoundError for a 404 or 410 response, and SchemaFetchError
    for any other failure, including a 401 for a refused token.
    """
    # Verify against the OS trust store. The uv-managed Python that uvx uses
    # has OpenSSL CA paths compiled for Debian (/etc/ssl/cert.pem), which do
    # not exist on RHEL, so the default context fails verification (#364).
    problem = url_problem(url)
    if problem:
        raise SchemaFetchError(f"refusing to fetch {url!r}: it {problem}")
    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    auth = {} if anonymous else auth_headers(url)
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
        if exc.code == 401 and auth:
            raise SchemaFetchError(
                f"could not fetch {url}: {exc}; {REFUSED_HINT}"
            ) from exc
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


def _gitlab_asset_url(links_url: str) -> str:
    """Return the schema asset's URL from a GitLab release's list of links.

    The API answers 404 both for a release that does not exist and, to a
    client without a token, for a project it may not see.
    """
    try:
        fetched = _http_get(links_url, {})
    except SchemaFetchError:
        raise
    except SchemaNotFoundError as exc:
        if auth_headers(links_url):
            raise
        raise SchemaNotFoundError(f"{exc}; {_no_token_hint(links_url)}") from exc
    try:
        links = json.loads(fetched.body or b"")
    except ValueError as exc:
        raise SchemaFetchError(f"{links_url} did not return JSON: {exc}") from exc
    for link in links if isinstance(links, list) else []:
        if (
            isinstance(link, dict)
            and link.get("name") == PUBLISHED_SCHEMA_ASSET
            and isinstance(link.get("url"), str)
        ):
            return link["url"]
    raise SchemaNotFoundError(
        f"{links_url} lists no {PUBLISHED_SCHEMA_ASSET} release asset"
    )


def _normal_path(path: str) -> str | None:
    """``path`` with its dot segments removed, as a server resolves them.

    ``%2e`` is decoded first, since servers treat it as ``.``. Returns None if
    a dot segment survives full decoding, for example one written with an
    encoded ``/``, which servers split differently.
    """
    path = re.sub("%2e", ".", path, flags=re.I)
    segments: list[str] = []
    for segment in path.split("/"):
        if segment == "..":
            if len(segments) > 1:
                segments.pop()
        elif segment != ".":
            segments.append(segment)
    if path.endswith(("/.", "/..")):
        segments.append("")
    normal = "/".join(segments)
    if any(part in (".", "..") for part in unquote(normal).split("/")):
        return None
    return normal


def _token_may_follow(links_url: str, asset_url: str) -> bool:
    """True if a release's asset link may be fetched with the token.

    The token is scoped to the links URL's origin: the link must be on it. As
    defence in depth the link must also be a package file,
    ``/api/v4/projects/<path or id>/packages/...`` (GitLab writes package
    links with the numeric project id, which this does not resolve), or under
    the project's web path, ``/<project path>/-/...``.
    """
    if url_problem(asset_url) or _origin(asset_url) != _origin(links_url):
        return False
    links_path = urlsplit(links_url).path
    match = re.fullmatch(r"(.*)/api/v4/projects/([^/]+)/releases/.+", links_path)
    if match is None:
        return False
    root, encoded = match.groups()
    project = unquote(encoded)
    path = _normal_path(urlsplit(asset_url).path)
    if path is None:
        return False
    api = re.escape(f"{root}/api/v4/projects/")
    return bool(
        re.match(rf"{api}(?:{re.escape(encoded)}|\d+)/packages/", path, re.I)
        or path.startswith(f"{root}/{project}/-/")
    )


def _fetch_gitlab_asset(
    links_url: str, asset_url: str, headers: dict[str, str]
) -> Fetched:
    """Fetch a GitLab release's schema asset, with a token only if in scope."""
    if _token_may_follow(links_url, asset_url):
        return _http_get(asset_url, headers)
    try:
        return _http_get(asset_url, headers, anonymous=True)
    except SchemaNotFoundError as exc:
        if not auth_headers(links_url):
            raise
        message = (
            f"{exc}; it was fetched without a token because the release links "
            f"it outside the project at {links_url}"
        )
        if isinstance(exc, SchemaFetchError):
            raise SchemaFetchError(message) from exc
        raise SchemaNotFoundError(message) from exc


def _is_derived_github_url(image: str, url: str) -> bool:
    """True if ``url`` is the GitHub release asset URL derived from ``image``."""
    try:
        on_github = _on_github(parse_image_ref(image))
        return on_github and url == published_schema_url(image)
    except SchemaNotFoundError:
        return False


def fetch_base_schema(image: str, recorded_url: str | None = None) -> dict:
    """Return the published base schema for ``image``.

    ``recorded_url`` is the instance's recorded schema URL, if any; see
    :func:`schema_source` for where the schema is fetched from.

    The cached copy for the image tag is revalidated with ``If-None-Match`` /
    ``If-Modified-Since``. The cached copy is also used when the fetch fails.
    An invalid cache record, or one that does not record the same source URL,
    is ignored and downloaded again; a record with no URL is taken to be for
    the GitHub URL derived from the image, the only one ibek fetched before
    records named their URL. A fetched schema without the shape of an ibek
    IOC schema is returned for the caller to refuse, and not cached.

    Raises:
        SchemaNotFoundError: no schema is published for the image.
        SchemaFetchError: the fetch failed and nothing is cached.
    """
    source = schema_source(image, recorded_url)
    url = source.url
    cache = _cache_path(image)
    validators_path = cache.with_suffix(".validators.json")
    cached = _read_json(cache)

    headers = {}
    validators = _read_json(validators_path) if cached is not None else None
    if (
        validators is not None
        and "url" not in validators
        and _is_derived_github_url(image, url)
    ):
        # Written before records named their URL, when ibek fetched only the
        # GitHub URL derived from the image.
        validators["url"] = url
    if validators is None or validators.get("url") != url:
        # The cached schema came from another source, for example before an
        # override was set, or does not say where it came from, so it is no
        # evidence of what ``url`` serves.
        cached = validators = None
    for key, header in (
        ("ETag", "If-None-Match"),
        ("Last-Modified", "If-Modified-Since"),
    ):
        if validators and isinstance(validators.get(key), str):
            headers[header] = validators[key]

    try:
        if source.links:
            asset_url = _gitlab_asset_url(url)
            fetched = _fetch_gitlab_asset(url, asset_url, headers)
        else:
            asset_url = url
            fetched = _http_get(url, headers)
    except SchemaFetchError as exc:
        if cached is None:
            raise
        print(f"Using cached schema for {image}, could not revalidate it: {exc}")
        return cached

    if fetched.body is None:
        if cached is None:
            raise SchemaFetchError(f"{asset_url} returned 304 but nothing is cached")
        return cached
    try:
        schema = json.loads(fetched.body)
    except json.JSONDecodeError as exc:
        raise SchemaNotFoundError(f"{asset_url} did not return JSON: {exc}") from exc

    if schema_shape_problem(schema):
        # Not cached: the caller refuses it, and a later run must fetch again
        # rather than revalidate it.
        return schema
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


def schema_shape_problem(schema: object) -> str | None:
    """Return why ``schema`` is not an ibek IOC schema ibek can merge into."""
    if not isinstance(schema, dict):
        return "is not a JSON object"
    properties = schema.get("properties")
    entities = properties.get("entities") if isinstance(properties, dict) else None
    items = entities.get("items") if isinstance(entities, dict) else None
    if not isinstance(items, dict):
        return "has no properties.entities.items object"
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return "has a $defs that is not an object"
    union: object = items
    if "$ref" in items:
        ref = items["$ref"]
        name = ref.split("/")[-1] if isinstance(ref, str) else None
        union = defs.get(name) if name else None
    if not isinstance(union, dict):
        return f"has an entities.items $ref {items.get('$ref')!r} not in $defs"
    if not isinstance(union.get("oneOf"), list):
        return "has no oneOf list of entity types"
    discriminator = union.get("discriminator")
    if not isinstance(discriminator, dict) or not isinstance(
        discriminator.get("mapping"), dict
    ):
        return "has no discriminator.mapping of entity types"
    return None


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


def generate_instance_schema(
    instance_dir: Path, candidate_url: str | None = None
) -> bool:
    """Generate ``<instance>/ioc.schema.json`` and rewrite the ``ioc.yaml`` header.

    ``candidate_url`` replaces the lock's recorded ``schema_url`` for this call,
    so a URL can be tried before it is recorded.

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
    recorded_url = (
        candidate_url
        if candidate_url is not None
        else RuntimeLock(instance_dir / RUNTIME_LOCK_NAME).schema_url
    )
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

    problem = schema_shape_problem(base)
    if problem:
        raise InvalidSchemaError(
            f"the base schema for {instance_dir.name} (image {image}) {problem}; "
            f"{schema_path} is left unchanged"
        )
    support_yamls = sorted(config_dir.glob("*.ibek.support.yaml"))
    merged = merge_entities(base, support_yamls)

    schema_path.write_text(json.dumps(merged, indent=2) + "\n")
    rewrite_ioc_yaml_header(config_dir / "ioc.yaml")
    return True
