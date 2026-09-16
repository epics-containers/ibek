# Vendor runtime support

Run `ibek pattern` in an IOC instance repository, usually outside the IOC
container. It copies support YAML and runtime files from a pattern library
into an instance's `config/`, recording the source, version, and file hashes in
`runtime-lock.yaml`. This adds configuration and templates to an existing
image; it does not install compiled drivers.

## Add and update

A reference is `[library:]name[@version]`. The built-in libraries are
`ibek-runtime-streamdevice` and `ibek-runtime-support`, both in the
[epics-containers GitHub organization](https://github.com/epics-containers).
Use an explicit version for reproducible instances:

```bash
ibek pattern add ibek-runtime-streamdevice:lakeshore340@1.0.0 services/my-ioc
ibek pattern update services/my-ioc --name lakeshore340 --version 1.1.0
```

These examples assume the named pattern and tag exist in your library. The
instance argument defaults to `.`. Without a library qualifier ibek tries
registered libraries in order. Without a version it uses the remote default
branch and records `HEAD`; that is not an immutable pin.

Use `--source` to test a local library:

```bash
ibek pattern add lakeshore340@work services/my-ioc --source /workspaces/my-patterns
```

Local sources use the current files in `<source>/<pattern>`; the version is
only a recorded label, not a checkout. `IBEK_PATTERN_LIBRARIES` can configure
additional named libraries; see {doc}`../reference/paths-and-environment`.

## Check and restore

```bash
ibek pattern check services/my-ioc
ibek pattern restore services/my-ioc --name lakeshore340
```

Vendored copies have a provenance header. Hashes cover those exact bytes and
detect local changes against the lock; they do not authenticate the upstream
tag. `restore` overwrites files from the recorded source and version without
changing the lock. `update` also refreshes hashes; without `--version` it
reuses the recorded version. Both remove files dropped by the selected
pattern. Omit `--name` to process every locked pattern.

`check` exits 1 for missing or modified locked files. `--allow-dirty`, or
`IBEK_ALLOW_DIRTY=1`, downgrades **both** kinds of failure to warnings and exits
0. A deliberate exception can instead be recorded as a quoted lock value
such as `"DIRTY # testing a protocol change"`; that entry is skipped with a
warning, even if the file is missing. A missing or empty lock has nothing to
check and succeeds. Extra untracked files are not checked.

## Instance schemas

`add`, `update`, and `restore` also regenerate `<instance>/ioc.schema.json`.
To regenerate after editing local support definitions:

```bash
ibek pattern schema services/my-ioc
```

ibek finds the image in the first existing file among `values.yaml`,
`compose.yml`, and `compose.yaml`, downloads or revalidates its published base
schema, and adds entities from top-level `config/*.ibek.support.yaml` files.
Existing base entity types are retained, not overridden. It also updates the
first-line schema comment in `config/ioc.yaml` to reference
`../ioc.schema.json`.

If no suitable image is found, or the image has no published schema (a 4xx
response), schema generation prints a message and leaves the existing schema
untouched; this is not a command failure. Vendoring still completes.

If the server cannot be reached, ibek uses the cached base schema for the image
tag. With no cached copy, an existing `ioc.schema.json` makes the command exit
1, because that schema may belong to a previous image. Vendored files and the
lock are already written when this happens. Without an existing schema, the
command prints a message and skips generation.

Commit the vendored files, lock, schema, and changed YAML header together.
At startup, `runtime generate2` reads the support definitions and
`runtime place-files` copies top-level protocol and database files into their
runtime search paths. Keep these artifacts at the top level of `config/`:
although vendoring preserves subdirectories, placement and instance-schema
collection are not recursive.

## Schema caching

Downloaded base schemas are cached in `~/.cache/ibek/schemas`, shared across
virtual environments. Every run revalidates a matching cache entry with a
conditional request, so a release asset uploaded again for the same tag
replaces the cached copy. The cached copy is also used when GitHub cannot be
reached, so recreating a venv does not reproduce a first download.

Set `IBEK_SCHEMA_CACHE` to a new empty directory to test a fresh download.
See {ref}`published-schema-cache` for the cache keys, reuse rules and a
copyable fresh-cache command.
