# Vendor runtime-support patterns into a services repo

`ibek pattern` copies a runtime-support *pattern* — a StreamDevice protocol
set, an AreaDetector plugin set, or any `*.ibek.support.yaml` plus its
`.proto` / `.protocol` / `.template` / `.db` — from a central library into a
single IOC instance, at a pinned version. The copies live under the instance's
`config/` and are recorded in a `runtime-lock.yaml` at the instance root, so the
committed instance alone answers "what is this IOC running?".

This page is a set of task recipes for services-repo maintainers and IOC
operators. For *why* it works this way, see
[ADR 0003](../explanations/decisions/0003-vendored-pattern-tag-is-authority.md)
and
[ADR 0004](../explanations/decisions/0004-vendor-runtime-support-over-submodules.md);
for where vendoring sits in the build pipeline, see the
[architecture overview](../explanations/architecture.md).

```{important}
The two central libraries are **`ibek-runtime-streamdevice`** and
**`ibek-runtime-support`**. A pattern reference is written
`[library:]name[@version]`, e.g. `ibek-runtime-streamdevice:lakeshore340@1.0.0`.
```

## Mental model

- Vendored files are **real copies, not symlinks**. Each carries a header line
  `# Vendored from <source>@<version> — DO NOT EDIT` and is reproduced
  byte-for-byte from the upstream library at its tag.
- `runtime-lock.yaml` records a per-file **SHA-256** that is a **local-drift
  integrity check only**. It detects hand-edits to vendored files in the
  instance — it is *not* a tamper-evident pin against the upstream library and
  *not* a content store.
- The **upstream library tag is the source of truth**, and tags are treated as
  immutable. `restore` and `update` (without a new version) both re-fetch the
  same tag and therefore reproduce identical bytes.

## 1. Add a pattern

Vendor a pattern into an instance. The files are written into `config/`, the
`runtime-lock.yaml` is created or updated, and the instance's `ioc.schema.json`
is regenerated.

```bash
ibek pattern add ibek-runtime-streamdevice:lakeshore340@1.0.0
```

```{note}
Schema regeneration is soft-skipped (reported, not an error) when `values.yaml`
pins no published image or the published base schema cannot be fetched. The
pattern is still vendored and the lock still updated.
```

The instance argument is the **second** positional and defaults to `.` (the
current directory), so run the command from inside the IOC instance folder, or
name it explicitly:

```bash
ibek pattern add ibek-runtime-streamdevice:lakeshore340@1.0.0 services/bl01t-ea-ts-01
```

By default the library name resolves to its published source. Override it with
`--source` / `-s`, which accepts a git URL or a local path — useful for testing
an unreleased pattern:

```bash
ibek pattern add streamdevice:lakeshore340@1.0.0 -s /path/to/local/library
```

## 2. Verify integrity

`ibek pattern check` recomputes the SHA-256 of every vendored file and compares
it against `runtime-lock.yaml`:

```bash
ibek pattern check services/bl01t-ea-ts-01
```

A clean instance prints `<instance>: vendored files match the lock` (the
message is prefixed with the instance path). Any hash mismatch (an
edited vendored file) or a missing file is an **error and exits 1** — this is
what your pre-commit hook and CI should rely on.

```{warning}
`--allow-dirty` (or the environment variable `IBEK_ALLOW_DIRTY=1`) downgrades
hash mismatches to *warnings* and exits 0. Treat it as an escape hatch for
intentional local edits only — it makes `check` still print "vendored files
match the lock", which is misleading in logs.
```

To keep a *deliberate* edit visible and sanctioned instead, set that file's lock
entry value to `DIRTY # <reason>`. Such entries are tolerated by `check` even
without `--allow-dirty`, so the divergence is recorded in the committed lock
rather than hidden behind a flag.

## 3. Re-pin to a new version

`ibek pattern update` re-vendors a pattern, refreshes the recorded hashes, and
rebuilds the schema. With no `--version` it re-fetches the same tag; with
`--version` / `-v` it moves the pin:

```bash
ibek pattern update --name lakeshore340 --version 1.1.0
```

```{note}
`--name` / `-n` is a **filter option, not a positional argument**. Omit it to
update every pattern in the lock. `--version` / `-v` and `--source` / `-s` are
likewise options.
```

## 4. Restore after hand-edits

If a vendored file has drifted (`check` reports a mismatch you did not intend),
revert it to the version pinned in the lock:

```bash
ibek pattern restore --name lakeshore340
```

`restore` re-clones the recorded tag and overwrites the vendored files, leaving
the lock unchanged. Omit `--name` to restore all patterns in the instance.

## 5. Regenerate the schema

`ibek pattern schema` rebuilds the instance's `ioc.schema.json` and rewrites the
header of `config/ioc.yaml` so the editor picks up the new schema. It fetches
the published base schema for the instance's pinned image and merges in the
vendored and local support entities:

```bash
ibek pattern schema services/bl01t-ea-ts-01
```

`add`, `update`, and `restore` all run this step for you; call it directly when
you have only changed local support definitions, or after a manual lock edit.

## Operational notes

- **Hooks and CI are strict.** The services-template-helm `ci_verify.sh` and the
  `pattern-check` pre-commit hook run `ibek pattern check` **without**
  `--allow-dirty`, so any unmarked drift fails the commit or build. Use a
  `DIRTY # <reason>` lock entry — not the flag — to land an intended divergence.
- **Loop exit status masks failures.** A `for` loop over instances exits with
  the status of the *last* iteration only, so an earlier failing instance can be
  masked by a later passing one. Keep `|| rc=1` plus `exit "${rc}"` in the hook,
  and set `require_serial: true` so pre-commit does not partition one instance's
  files across parallel workers.
- **Pin the ibek version through `requirements.txt`.** In hooks, resolve ibek
  with `uvx --from ibek --constraints requirements.txt ibek pattern check` so
  `requirements.txt` stays the single source of truth. Note that a `>=X`
  specifier excludes pre-releases — pin `==Xb2` during a beta window.

## Artifacts at a glance

| File | Location | Role |
| --- | --- | --- |
| Vendored pattern files | `<instance>/config/` | Real copies with the DO-NOT-EDIT header; placed into the IOC at boot. |
| `runtime-lock.yaml` | `<instance>/` | Per-pattern version + source label + per-file SHA-256 (local-drift check). |
| `ioc.schema.json` | `<instance>/` | Self-contained schema merging the base image schema with vendored + local support. |
