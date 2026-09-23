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
destination argument (shown as `DEST` in `--help`, because vendoring is not
IOC-specific) defaults to `.`, so run the command from inside the IOC instance
folder, or name it explicitly. Without a library qualifier ibek tries
registered libraries in order. Without a version it uses the remote default
branch and records `HEAD`; that is not an immutable pin.

```{warning}
`ibek` reads and writes exactly one `runtime-lock.yaml` shape: a `version:` /
`patterns:` root, with keys relative to the instance root
(`config/x.proto`, not `x.proto`). `add`, `update` and `check` all refuse a
lock in any other shape outright. See
[Unrecognised locks](#unrecognised-locks) below for what to do about one.
```

Use `--source` to test a local library:

```bash
ibek pattern add lakeshore340@work services/my-ioc --source /workspaces/my-patterns
```

Local sources use the current files in `<source>/<pattern>`; the version is
only a recorded label, not a checkout. `IBEK_PATTERN_LIBRARIES` can configure
additional named libraries; see {doc}`../reference/paths-and-environment`.

## What gets vendored

A pattern folder may carry an **`ibek.manifest.yaml`** declaring which of its
files are vendored and where they land. This is how a library keeps browsable
documentation alongside its runtime files without shipping the docs into an IOC:

```yaml
version: 1
vendor:
  - src: '.*\.(template|proto|protocol|db|req|ibek\.support\.yaml)$'
    dest: config
```

`src` is a regular expression matched (with `re.fullmatch`) against each file's
path relative to the pattern folder; `dest` is a folder relative to the instance
root, joined with that path so nesting is preserved. The list is an ordered,
first-match-wins **allow-list** — a file matched by no entry is not vendored.

**A pattern with no manifest is vendored through a default manifest ibek
supplies**: every file, into `config/` (see
[No manifest](../reference/pattern-manifest.md#no-manifest)). You only need to
write one when a pattern contains files that must *not* reach the instance.
The full format, including validation rules, is in the
[manifest reference](../reference/pattern-manifest.md).

## Check and restore

```bash
ibek pattern check services/my-ioc
ibek pattern restore services/my-ioc --name lakeshore340
```

Vendored files are real copies, byte-for-byte identical to the upstream
library at its tag. `runtime-lock.yaml` records a per-file SHA-256 that
`check` uses to detect local changes to those files; it is a local-drift
integrity check only, not a tamper-evident pin against the upstream library.
`restore` overwrites files from the recorded source and version without
changing the lock. `update` also refreshes hashes; without `--version` it
reuses the recorded version. Both remove files dropped by the selected
pattern. Omit `--name` to process every locked pattern.

`check` exits 1 for missing or modified locked files. `--allow-dirty`, or
`IBEK_ALLOW_DIRTY=1`, downgrades **both** kinds of failure to warnings and exits
0. A deliberate exception can instead be recorded as a quoted lock value
such as `"DIRTY # testing a protocol change"`; that entry is skipped with a
warning, even if the file is missing. A missing or empty lock has nothing to
check and succeeds. Extra untracked files are not checked.

### Unrecognised locks

`ibek` reads and writes exactly one `runtime-lock.yaml` shape: a `version:` /
`patterns:` root, with keys relative to the instance root (`config/x.proto`,
not `x.proto`). `check`, `add` and `update` refuse a lock in any other shape,
printing something like:

```
error: <instance>/runtime-lock.yaml: lock format not recognised; convert it
with 'uv run scripts/convert-runtime-lock.py <lock>' ...
```

Convert the lock in place, from an `ibek` checkout:

```bash
uv run scripts/convert-runtime-lock.py <instance>/runtime-lock.yaml
```

This rewrites the lock's own text only — it never touches the vendored files,
so their recorded hashes still verify. Re-run `check`; from there `add`,
`update` and `restore` all work on the converted lock exactly as on any other.
The script is standalone (a `scripts/` entry point carrying its own PEP 723
dependency), not part of the installed `ibek` package, so it runs against any
instance's lock without first vendoring anything.

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

If no suitable image is found, or the image has no published schema (a 404 or
410 response), schema generation prints a message and leaves the existing schema
untouched; this is not a command failure. Vendoring still completes.

If the fetch fails for any other reason, such as a network or TLS error, a
server error, or a 403 or 429 response, ibek uses the cached base schema for the
image tag. With no cached copy, an existing `ioc.schema.json` makes the command exit
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
replaces the cached copy. A cache entry written by an older ibek has no stored
validators: ibek downloads that entry once, then revalidates it on later runs.
The cached copy is also used when a fetch fails, so recreating a venv does not
reproduce a first download.

Set `IBEK_SCHEMA_CACHE` to a new empty directory to test a fresh download.
See {ref}`published-schema-cache` for the cache keys, reuse rules and a
copyable fresh-cache command.
