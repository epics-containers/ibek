# Paths and environment

## Container paths

`EPICS_ROOT` defaults to `/epics`. Set it before starting ibek to relocate
paths derived from that root. Image scripts and EPICS tools may have their own
path settings; this variable does not rewrite them.

| Default path | Contents |
| --- | --- |
| `/epics/support` | Built support modules and `configure/RELEASE`. |
| `/epics/ibek-defs` | Installed support YAML definitions. |
| `/epics/pvi-defs` | Installed PVI device YAML. |
| `/epics/ioc/config` | Instance inputs; also searched for PVI and autosave overrides. |
| `/epics/runtime` | Generated `st.cmd`, `ioc.subst`, PVI templates, and wait list. |
| `/epics/runtime/protocol` | Instance StreamDevice protocols copied by `runtime place-files`. |
| `/epics/runtime/db` | Instance database templates copied by `runtime place-files`. |
| `/epics/opi` | Generated PVI operator screens and index. |
| `/epics/autosave` | Autosave request-file links. |

`runtime generate2 --output` changes its main output directory, not the PVI
screen directory or the paths used by other commands. In particular PVI
templates still use `$EPICS_ROOT/runtime`. Use the standard layout for a full
IOC startup, and `--no-pvi` when generating isolated examples elsewhere.
`ioc extract-runtime-assets --source` independently defaults to `/epics`.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `EPICS_ROOT` | Root of ibek's container paths; read when ibek starts. |
| `IBEK_SCHEMA_CACHE` | Directory for downloaded base schemas; default `~/.cache/ibek/schemas`. |
| `IBEK_SCHEMA_URL` | Base-schema URL for every instance in this run, over any recorded or derived URL; see {ref}`schema-url`. |
| `IBEK_GITLAB_HOSTS` | Comma-separated GitLab hostnames that may receive a token, e.g. `gitlab.diamond.ac.uk`; see {ref}`schema-auth`. |
| `GITLAB_TOKEN` | GitLab token sent as `PRIVATE-TOKEN` to a listed host or `CI_SERVER_HOST`; see {ref}`schema-auth`. |
| `CI_JOB_TOKEN`, `CI_SERVER_HOST` | Set by GitLab CI: the job token is sent as `JOB-TOKEN` to `CI_SERVER_HOST` when `GITLAB_TOKEN` is unset. |
| `IBEK_PATTERN_LIBRARIES` | Add or override pattern sources: `name=uri,name2=uri2`. |
| `IBEK_ALLOW_DIRTY` | Exactly `1` makes `pattern check` report integrity failures as warnings. |

Templates can read the process environment through the `env` Jinja mapping;
see {doc}`jinja-context`. The path settings above and template environment
access are separate features.

(published-schema-cache)=
## Published schema cache

`pattern schema`, and the schema step of `pattern add`, `update`, and `restore`,
cache the **downloaded base schema**. The default directory is
`~/.cache/ibek/schemas`, outside the virtual environment. Recreating a venv or
running another ibek installation as the same user therefore reuses the cache.
`IBEK_SCHEMA_CACHE` overrides the directory; `XDG_CACHE_HOME` is not consulted.

The key is `<registry host>/<image path>/<image-tag>.json`, one directory
per part. For example:

```text
Image: ghcr.io/epics-containers/ioc-adsimdetector-runtime:2025.11.1
Asset: https://github.com/epics-containers/ioc-adsimdetector/releases/download/2025.11.1/ibek.ioc.schema.json
Cache: ~/.cache/ibek/schemas/ghcr.io/epics-containers/ioc-adsimdetector/2025.11.1.json
```

The last part of the image path loses a final `-developer` or `-runtime` and
its optional preceding `-linux` or `-rtems-beatnik`, so developer and runtime
variants share the base-schema cache entry. The registry host and every path
part are kept, so images of the same name on different registries have
separate entries. A port is written with `_` (`localhost_5000`), and an image
with no registry host is cached under `docker.io`.

Only the part before the tag is read as a registry host when it contains `.`
or `:` or is `localhost`, as in Docker's reference grammar;
`epics-containers/ioc-adaravis-runtime:2025.11.1` has no host.

The cache key comes from the image, whichever URL the schema was fetched
from. The validators file also records the source URL: the override, the
GitHub asset, or the GitLab release-links URL. A cache entry whose recorded
URL differs, for example after an override is set, or that records no URL, is
ignored and downloaded again.

(schema-url)=
## Published schema URL

ibek locates the base schema from the instance image:

| Registry | Where ibek looks |
| --- | --- |
| `ghcr.io`, `docker.io`, `index.docker.io`, `registry-1.docker.io` or none | `https://github.com/<org>/<repo>/releases/download/<tag>/ibek.ioc.schema.json` |
| a GitLab registry whose web host is listed in `IBEK_GITLAB_HOSTS` or is the CI job's server | the `ibek.ioc.schema.json` link of GitLab release `<tag>`, listed by `https://<web host>/api/v4/projects/<project path>/releases/<tag>/assets/links` |
| any other host, such as `quay.io` or `localhost:5000` | nothing: generation is skipped with a message |

For GitHub, `<org>` is the first part of the image path and `<repo>` the last
part. For a listed GitLab host, ibek follows GitLab's ioc-template, which
pushes `<registry>/<project path>/<project name>-<arch>-<target>:<tag>`:

- the web host is the registry host without its port and without a
  `registry.` prefix;
- the project path is the image path without its last part, URL-encoded.

ibek then downloads the link's `url`, the generic package file, sending the
token only if that URL is on the same origin as the links URL. The token is
scoped to that allowlisted origin, not to one project: anyone who can edit
the release can point its link at another project on the same server that the
token can read. As defence in depth, the link must also be a package file,
`/api/v4/projects/<project path or numeric id>/packages/...`, or under the
project's web path, `/<project path>/-/...`, after `.` and `..` segments are
resolved; ibek does not check that a numeric id is the same project. A link
anywhere else is fetched without a token, and so is every redirect after one
that leaves the origin.

For both GitHub and GitLab, the last part loses a final `-developer` or
`-runtime` and its optional `-linux` or `-rtems-beatnik`. For example:

```text
Image: gitlab.diamond.ac.uk:5050/controls/containers/iocs/ioc-dlslinuxvac/ioc-dlslinuxvac-linux-runtime:2026.11.3
Links: https://gitlab.diamond.ac.uk/api/v4/projects/controls%2Fcontainers%2Fiocs%2Fioc-dlslinuxvac/releases/2026.11.3/assets/links
Asset: https://gitlab.diamond.ac.uk/api/v4/projects/6713/packages/generic/ioc-schema/2026.11.3/ibek.ioc.schema.json
```

The releases API is used rather than the release's
`/-/releases/<tag>/downloads/` permalink because the API accepts a token for
a non-public project and answers `404` or `401` instead of redirecting to a
sign-in page, and because it also finds a schema link that has no
`direct_asset_path`.

Two overrides replace the derived location, highest precedence first. Both
must be plain `https://` URLs: ibek refuses any other scheme (`file:`, `ftp:`,
`data:`, `http:` or none), user information (`user@`) and backslashes, when it
reads the lock, the `--schema-url` option or `IBEK_SCHEMA_URL`, and again once
the placeholders are filled. It fetches only over HTTPS: no handler for any
other scheme is installed, and a redirect to a refused URL fails.


1. **`IBEK_SCHEMA_URL`**: a one-off for every instance in this run, for
   example to try a URL before recording it.
2. **`schema_url` in the instance's `runtime-lock.yaml`**: recorded with the
   instance, so everyone who opens the repository, and CI, fetches the same
   URL. Record or clear it with:

   ```bash
   ibek pattern schema services/my-ioc --schema-url 'https://example.org/{tag}/ibek.ioc.schema.json'
   ibek pattern schema services/my-ioc --schema-url ''
   ```

   `--schema-url` first generates the schema from the new URL, and records the
   URL only if that succeeds; a URL that serves no schema exits 1 and leaves
   the lock unchanged. It refuses to run while `IBEK_SCHEMA_URL` is set,
   because that variable would replace the URL being tried.

An override is fetched as it is, with no release-links lookup. It may contain
these placeholders, filled from the instance image:

| Placeholder | Value |
| --- | --- |
| `{registry}` | Registry host, with any port; `docker.io` when the image names none. |
| `{project}` | Image path without its last part. |
| `{project_encoded}` | `{project}` with each `/` encoded as `%2F`, as the GitLab API wants a project path. |
| `{name}` | Last part of the image path, without its developer/runtime suffix. |
| `{tag}` | Image tag. |

Any other `{...}` is an error. Use `{tag}` so that the URL follows image
upgrades; for a GitLab project, for example,
`https://gitlab.diamond.ac.uk/api/v4/projects/{project_encoded}/packages/generic/ioc-schema/{tag}/ibek.ioc.schema.json`. A lock with a `schema_url` is written as `version: 3`; ibek releases
that read only versions 1 and 2 refuse it with "unsupported lock version 3",
rather than dropping the URL. An instance without vendored patterns can still
have a lock that records only a `schema_url`. Every tool that runs
`ibek pattern check` on such an instance, such as a services repository's CI
and pre-commit hooks, needs an ibek that reads version 3.

(schema-auth)=
## Schema download authentication

ibek looks schemas up only on GitLab hosts the operator lists, and sends a
GitLab token only to them, never to a host named only by repository content:
image refs and schema URLs are repository text, and a change that pointed
them at another host would otherwise collect the token of whoever ran the
hook or the CI job. A schema on a public project of a listed host downloads
without a token.

| Variable | Meaning |
| --- | --- |
| `IBEK_GITLAB_HOSTS` | Comma-separated `host[:port]` entries: the GitLab servers ibek looks schemas up on and may send a token to. A bare host means the default HTTPS port only. At DLS: `IBEK_GITLAB_HOSTS=gitlab.diamond.ac.uk`. |
| `GITLAB_TOKEN` | Sent as `PRIVATE-TOKEN` to a listed host or to `CI_SERVER_HOST`. A personal, group or project access token with `read_api` scope. |
| `CI_JOB_TOKEN`, `CI_SERVER_HOST`, `CI_SERVER_PORT` | Set by GitLab CI; the job's server counts as listed. Without `GITLAB_TOKEN`, the job token is sent as `JOB-TOKEN`, and only to that server. |

Hostnames are compared without regard to case, and ports must match. A token
is sent only over HTTPS, never to `github.com`, `ghcr.io` or
`githubusercontent.com` even if listed, and only to the host the URL names. A redirect keeps the token only
when it stays on the same scheme, host and port; a redirect to any other
origin is followed without it.

`PRIVATE-TOKEN` has been checked against gitlab.diamond.ac.uk on the releases
API and the generic package download, for public and internal projects.
`JOB-TOKEN` has not been checked there: GitLab documents job-token access to
releases and generic packages, but another project must allow the job in its
job token settings.

How GitLab answers decides what ibek reports:

| Response | Result |
| --- | --- |
| `404` with no token sent | Skipped: the project may be private or may not exist; the message names `IBEK_GITLAB_HOSTS` and `GITLAB_TOKEN`. |
| `404` with a token sent | Skipped: no such project or release. |
| `401` with a token sent | Failed fetch: the token was refused, or the project does not exist. |
| Release lists no `ibek.ioc.schema.json` | Skipped: nothing published. |
| Redirect to a path ending in `/users/sign_in` (an override URL on a GitLab web route) | Skipped with no token sent; a failed fetch with one. |
| Asset outside the project, fetched without a token, not found | Skipped; the message says the token was withheld. |

A fetched schema must have the shape of an ibek IOC schema: a JSON object
whose `properties.entities.items` (inline or through a `$ref` into `$defs`)
has a `oneOf` list and a `discriminator.mapping`. Anything else stops the
command with exit 1, and the instance's `ioc.schema.json` is left unchanged.

A failed fetch uses the cached schema, or with no cached copy exits 1 when an
`ioc.schema.json` already exists, as described below.

Next to each cache file, `<key>.validators.json` stores the `ETag` and
`Last-Modified` response headers. On every run ibek sends them back as
`If-None-Match` and `If-Modified-Since`:

| Response | Result |
| --- | --- |
| `304 Not Modified` | The cached schema is used. |
| `200` | The cache file is replaced; a changed schema prints `Published schema for <image> changed since it was cached`. |
| `404`, `410` | No schema is published: generation is skipped. |
| Other 4xx (for example `403`, `429`), 5xx, network or TLS error | The fetch failed: the cached schema is used, with a warning. With no cached copy, see below. |

On a miss ibek downloads the release asset and caches successfully parsed JSON.
Failed downloads are not cached. Both files are written atomically. A cache
file without a validators file, for example from an older ibek, is downloaded
again once. An unreadable or invalid cache file is ignored and downloaded again.

If the fetch fails and nothing is cached for the tag, an existing
instance `ioc.schema.json` makes the command exit 1, because that schema may
belong to a previous image. Without an existing schema, generation is skipped.

The instance's `ioc.schema.json` is a separate, generated file. Each successful
schema run rebuilds it from the base schema plus top-level
`config/*.ibek.support.yaml` files; its existence does **not** prevent a
base-schema download. Pattern source repositories also have no persistent
ibek cache: remote sources are cloned into a temporary directory each time,
while local sources are copied from their current working tree.

To reproduce a first download without deleting the shared cache:

```bash
schema_cache=$(mktemp -d)
IBEK_SCHEMA_CACHE="$schema_cache" ibek pattern schema services/my-ioc
```

Reusing that directory for a second invocation exercises a revalidated cache
hit. A new
empty directory exercises another miss. The command still updates the
instance schema and `config/ioc.yaml` header on success, so inspect their diff
afterward. See {doc}`../how-to/troubleshoot` for failed or stale schema results.
