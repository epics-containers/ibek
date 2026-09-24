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
`epics-containers/ioc-adaravis-runtime:2025.11.1` has no host. Images on a
GitLab registry get no schema yet: ibek reports that GitLab-published schemas
are not supported and skips generation (#375).

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
