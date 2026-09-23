# 5. A pattern declares what is vendored

## Status

Accepted

## Context

`ibek pattern` hard-coded its vendoring policy: every file in a pattern folder
was copied into `<instance>/config/` and hashed into `runtime-lock.yaml`. That is
exactly right for a flat StreamDevice pattern and wrong for everything else.

The immediate driver is documentation. We want the useful docs from each source
module to live in `ibek-runtime-streamdevice` alongside the protocol and template
files, so the library is browsable and self-explanatory. Those docs must *not* be
vendored into an IOC instance — they are repo context, not runtime files, and
`config/` is the Kubernetes ConfigMap payload. There was no way to express that.

The second driver is forward compatibility with build-time support management,
which needs the same declarative description of "which files go where" against a
different library and a different destination.

## Decision

A pattern folder may carry an **`ibek.manifest.yaml`** declaring which of its
files are vendored and where they land:

```yaml
version: 1
vendor:
  - src: '.*\.(template|proto|protocol|db|req|ibek\.support\.yaml)$'
    dest: config
```

- **It is an allow-list.** A file matched by no entry is not vendored. That is
  the mechanism that keeps `docs/` out of `config/`.
- **The list is ordered and first-match-wins.** Without that, one file could land
  in two places under two lock keys, and both `check` and orphan-pruning become
  ambiguous about which copy is authoritative.
- **A pattern with no manifest is vendored through a synthesised default**
  (`src: '.*'`, `dest: config`) rather than through a second code path. One
  vendoring path, one check path, no branches — and the default is covered by
  the same validation and the same tests as a hand-written manifest. A pattern
  gets a manifest if and only if it contains files that must not be vendored.
- **Validation is whole-manifest and fails hard, before a single file is
  written.** A skipped-with-warning entry would mean a file that should be in the
  IOC silently is not, which is not acceptable in an integrity system. Every
  message names the offending entry.
- **Lock keys are relative to the destination root**, always — not to `config/`.
  The synthesised default (a pattern with no manifest) produces `config/...`
  keys naturally, so there is no per-pattern base field and no branch in
  `check`.

The lock has a `version:` / `patterns:` root wrapper, because a bare
`{pattern_name: entry}` mapping has nowhere to put metadata: `version:` gives
the format room to evolve, `patterns:` holds each vendored pattern by name.

`ibek` reads and writes exactly this one shape. A lock in any other shape is
refused outright, with a generic message naming a standalone conversion
script rather than describing what the other shape is or how it arose — a
description that would go stale the moment the lock format changes again.
Reading such a lock as an *empty* one is the one thing that must never happen:
`check` would then pass having verified nothing, and the instance would
silently become unmanaged.

## Consequences

- Switching a pattern's manifest can prune an emptied `config/` itself, since
  orphan pruning now walks up to the destination root. Correct, but startling in
  a diff.
- Orphans are computed from the **old lock's** key list and new files from the
  **new** plan, so `update` across a version that gains a manifest removes
  exactly the files the manifest stopped matching.
- `dest` may also be a substitution (`\1` / `\g<name>`), expanding to the whole
  destination-relative path for flattening, renaming or re-rooting. It is kept
  out of the user-facing tutorial: `dest: config` is the only form a services
  repo needs. `..` is therefore checked *after* expansion, since a capture group
  can introduce one.
- A vendored `*.ibek.support.yaml` must land at the `config/` root, because
  `ibek pattern schema` merges `config/*.ibek.support.yaml` **non-recursively**.
  A misrouted one vendors cleanly, checks cleanly, and is then silently missing
  from the instance's editor schema. (`ibek runtime generate2` globs
  `config/**/*.ibek.support.yaml` and does find a nested one, so the IOC itself
  still boots — what is lost is editor validation.) The rule is conditional on
  the file being vendored at all.
- Two sources mapping to one destination is a hard error, not a last-writer-wins
  overwrite that `check` would then pass — and destinations are compared in
  normal form, so `config/x` and `config/./x` are recognised as the one file
  they are. Likewise one destination cannot be both a file and the folder
  holding another, which would otherwise fail half way through the write.
- `dest` is the only user-controlled placement, and `ibek runtime place-files`
  copies `*.proto` / `*.db` / `*.template` from the `config/` root only. Nesting
  those under `config/` is for repo organisation; they will not reach the IOC's
  runtime search path. Closing that gap belongs to `place-files`, not here.

## Rejected

- **A `lock:` key in the manifest.** A pattern can never be the authority on
  where a *destination's* lock lives. `runtime-lock.yaml` at the destination
  root, always.
- **A `stamp:` key** — moot once the vendored header is dropped (see
  [ADR 4](./0004-vendor-runtime-support-over-submodules.md)).
- **A per-pattern `root:` field in the lock, or a "has manifest" flag.**
  Destination-root-relative keys make both unnecessary, and `check` is offline
  and cannot see the manifest anyway. The version pin already pins it.
- **Making the lock's `version:` a switch ibek branches on to read an older
  shape.** It exists for future evolution and validation only; a shape ibek
  does not recognise is refused, and converting it is a standalone step
  outside ibek entirely (`scripts/convert-runtime-lock.py`).
- **A `{pattern}` token in `dest`, a `requires:` key, dependency resolution, and
  one lock spanning several destinations.** All belong to the build-time support
  issue, and none of them need a format break — which is why the manifest root is
  a mapping rather than a bare list.

See [ADR 3](./0003-vendored-pattern-tag-is-authority.md) for where the authority
for a pattern's *content* lives, and the
[pattern manifest reference](../../reference/pattern-manifest.md) for the format.
