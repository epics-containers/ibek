# 4. Vendor runtime support over submodule + symlink

## Status

Accepted

## Context

An IOC instance needs its runtime-support file-set: StreamDevice protocol
files, AreaDetector plugin sets, support `*.ibek.support.yaml`, and the
associated `.proto`/`.protocol`/`.template`/`.db`. Historically these were
consumed by pointing the instance at a central support module via a git
submodule and symlinks into it.

That coupling made "what is this IOC actually running?" hard to answer from the
committed instance alone: the answer depended on the submodule commit and on
whatever the symlinks resolved to in the build image, so a pattern's version was
tied to the image rather than to the instance.

## Decision

Consume runtime support as **per-instance vendored copies**, pinned by a
`runtime-lock.yaml` at the instance root, instead of submodule + symlink.

`ibek pattern add|update|check|restore|schema` copies a pattern's file-set from
a central library (e.g. `ibek-runtime-streamdevice`, `ibek-runtime-support`)
into the instance's `config/`, prepends a deterministic
`# Vendored from <source>@<version> — DO NOT EDIT` header, and records each
file's SHA-256 in the lock. A self-contained `ioc.schema.json` is generated per
instance by merging the vendored support entities into the image's published
base schema.

## Consequences

- An instance gains a version axis for its support that is independent of the
  image: the committed lock answers "what is this IOC running?" with
  cryptographic certainty.
- Vendored files are real files (not symlinks) and carry a DO-NOT-EDIT header;
  `ibek pattern check` enforces their integrity against the lock so accidental
  edits are caught.
- `config/` remains the Kubernetes ConfigMap payload (runtime inputs only,
  bounded by the ConfigMap size limit), now self-contained rather than
  resolved through a submodule at build time.
- The central libraries become the single upstream source for patterns; see
  [ADR 3](./0003-vendored-pattern-tag-is-authority.md) for how their tags relate
  to the lock.
