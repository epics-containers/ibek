# Vendor runtime support

Run `ibek pattern` in an IOC instance repository, usually outside the IOC
container. It copies support YAML and runtime files from a pattern library
into an instance's `config/`, recording the source, version, and file hashes in
`runtime-lock.yaml`. This adds configuration and templates to an existing
image; it does not install compiled drivers. To build patterns into a generic
IOC image for all its instances, see {doc}`install-runtime-patterns`.

For why it works this way, see
[ADR 0003](../explanations/decisions/0003-vendored-pattern-tag-is-authority.md),
[ADR 0004](../explanations/decisions/0004-vendor-runtime-support-over-submodules.md)
and
[ADR 0005](../explanations/decisions/0005-pattern-manifest-declares-what-is-vendored.md).

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
{ref}`No manifest <no-manifest>`). You only need to
write one when a pattern contains files that must *not* reach the instance.
The full format, including validation rules, is in the
[manifest reference](../reference/pattern-manifest.md).

The manifest's file-set suits most instances. An instance that needs a
different set of files can record a selection in its lock; see
{doc}`select-pattern-files`.

## Vendor part of a pattern

A library pattern often defines many entity models when an instance uses one or
two. `--model` vendors only the files the named models load, and `--only` names
the files to vendor. For example, to take the bumpstrip monitor from the BL21I
pattern and none of its other templates:

```bash
ibek pattern add ibek-runtime-support:BL21I@0.4.0 . --model TTHBumpstripMonitor
```

or, naming the template file instead of the model:

```bash
ibek pattern add ibek-runtime-support:BL21I@0.4.0 . \
    --only BL21I_TTH_Bumpstrip_Monitor.template
```

Both vendor `config/BL21I.ibek.support.yaml` and
`config/BL21I_TTH_Bumpstrip_Monitor.template`, and record the choice under
`select:` in `runtime-lock.yaml`:

```yaml
version: 4
patterns:
  BL21I:
    version: 0.4.0
    source: github.com/epics-containers/ibek-runtime-support
    select:
      models:
      - TTHBumpstripMonitor
    files:
      config/BL21I.ibek.support.yaml: sha256:...
      config/BL21I_TTH_Bumpstrip_Monitor.template: sha256:...
```

- The pattern's support YAML is always vendored, whole and unmodified, so it
  still defines every model in the pattern.
- `--model` takes, from the support YAML, the `databases[].file` entries and
  the `pvi.yaml_path` of each named model and of the models it instantiates
  through `sub_entities`. For each database file it also vendors the autosave
  request files `<template>_settings.req` and `<template>_positions.req`. It
  vendors every protocol file (`*.proto`, `*.protocol`) the manifest vendors
  too, because a StreamDevice template names its protocol inside a record link,
  where the support YAML cannot see it.
- `--only` takes paths relative to the pattern folder, exactly. List every file
  the model needs: its templates, its pvi device file (`*.pvi.device.yaml`),
  its autosave request files (`*.req`) and the protocol files its templates
  use.
- Both options can be repeated and combined; the files of all of them are
  vendored. Files keep the destinations the manifest gives them.

An unknown model or file fails before anything is written, listing the models
or files the pattern has. `update` resolves `--model` against the release it
moves to, so a model whose template is renamed still gets the right file; an
`--only` file that the release no longer has is an error. `restore` vendors the
same files again.

An entity whose model's database or pvi device files were left out fails
`ibek runtime generate2` with, for example:

```
Error: entity BL21I.ARMAirControl uses model ARMAirControl whose files were not
vendored from pattern BL21I (BL21I_ARM_Air_Control.template is missing); re-add
with `ibek pattern add <library>:BL21I@0.4.0 <instance> --model ARMAirControl`,
keeping the models and files already selected
```

`generate2` makes this check when the instance's `runtime-lock.yaml` sits beside
its config folder, as it does in a services repo, so pre-commit and CI catch it.
See {doc}`select-pattern-files` for the full selection rules.

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

The library tag is the source of truth and is treated as immutable: `restore`,
and `update` without `--version`, reproduce the same bytes; to change what an
instance runs, move the pin with `update --version`.

Vendored files carry no marker of their own, so `ibek pattern check` is the
only guard against a silent edit. The services-template-helm pre-commit hook
and `ci_verify.sh` run it without `--allow-dirty`, so record an intended
divergence with a `DIRTY # <reason>` lock entry rather than the flag:
`--allow-dirty` still prints `vendored files match the lock`, which reads as
clean in logs. Any formatter or whitespace-fixing hook must exclude the
vendored files under `config/`.

(unrecognised-locks)=

### Unrecognised locks

`ibek` reads and writes exactly one `runtime-lock.yaml` shape: a `version:` /
`patterns:` root, with keys relative to the instance root (`config/x.proto`,
not `x.proto`). `check`, `add` and `update` refuse a lock in any other shape,
printing something like:

```
error: <instance>/runtime-lock.yaml: lock format not recognised; convert it
with 'uv run scripts/convert-runtime-lock.py <lock>' ...
```

Convert the lock in place. From an `ibek` checkout:

```bash
uv run scripts/convert-runtime-lock.py <instance>/runtime-lock.yaml
```

From anywhere else — a services repo with no `ibek` checkout — run it straight
from its raw URL on the branch or tag you want:

```bash
uv run https://raw.githubusercontent.com/epics-containers/ibek/main/scripts/convert-runtime-lock.py <instance>/runtime-lock.yaml
```

This rewrites the lock's own text only — it never touches the vendored files,
so their recorded hashes still verify. Re-run `check`; from there `add`,
`update` and `restore` all work on the converted lock exactly as on any other.
The script is standalone (a `scripts/` entry point carrying its own PEP 723
dependency), not part of the installed `ibek` package, so `uv run` fetches and
runs it — whether given a local path or a URL — without first vendoring
anything.

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

The base schema is located from the image: a GitHub release asset for an
image on `ghcr.io` or Docker Hub, or the schema link of a GitLab release for
an image on a GitLab host listed in `IBEK_GITLAB_HOSTS` (at DLS,
`IBEK_GITLAB_HOSTS=gitlab.diamond.ac.uk`). Other registries are skipped. For a
non-public GitLab project, also set `GITLAB_TOKEN`; ibek sends a token to no
unlisted host. If an image's schema lives elsewhere, record its `https://` URL with the
instance:

```bash
ibek pattern schema services/my-ioc --schema-url 'https://example.org/{tag}/ibek.ioc.schema.json'
```

This generates the schema from that URL and, if that works, writes
`schema_url` to `runtime-lock.yaml`. For a single run,
`IBEK_SCHEMA_URL` overrides both. See {ref}`schema-url` and
{ref}`schema-auth`.

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

## Artifacts at a glance

| File | Location | Role |
| --- | --- | --- |
| Vendored pattern files | `<instance>/config/` | Real copies, byte-identical to the library at its tag; placed into the IOC at boot. |
| `ibek.manifest.yaml` | `<library>/<pattern>/` | Optional, in the *library*: declares which files are vendored and where. Never vendored itself. |
| `runtime-lock.yaml` | `<instance>/` | Per-pattern version + source label + per-file SHA-256 (local-drift check), keyed relative to the instance root; optional `schema_url`. |
| `ioc.schema.json` | `<instance>/` | Self-contained schema merging the base image schema with vendored + local support. |
