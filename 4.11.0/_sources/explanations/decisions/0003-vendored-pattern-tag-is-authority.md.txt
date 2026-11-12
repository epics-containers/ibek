# 3. Vendored pattern tag is the authority

## Status

Accepted

## Context

`ibek pattern` vendors a runtime-support pattern from a central library into an
IOC instance at a pinned version. The files are copied into the instance's
`config/` with a `# Vendored from <source>@<version> — DO NOT EDIT` header, and
each file's SHA-256 is recorded in `runtime-lock.yaml` at the instance root.

This raises the question of where the *authority* for a pattern's content lives:
the upstream library at its tag, or the hashes captured in the lock. The two
answers lead to materially different behaviour for `update` and `restore`, and
to whether the lock must defend against upstream content changing under a tag.

## Decision

The **upstream library at its tag is the source of truth**, and tags are
treated as **immutable** (a published tag is never moved to a new commit).

The `runtime-lock.yaml` SHA-256 entries are an **integrity check for local
drift only** — they let `ibek pattern check` detect hand-edits to vendored
files. They are deliberately *not* a content store and *not* a tamper-evident
pin against the upstream library.

## Consequences

- `restore` re-clones the pattern at the recorded tag and overwrites the
  vendored files, trusting the fetched bytes. It does not verify them against
  the recorded hashes and keeps the lock unchanged.
- `update` with no `--version` re-vendors the *same* tag and re-records the
  hashes; `update --version X` moves the pin. Because tags are immutable,
  `update` with no `--version` and `restore` produce identical bytes, and
  `check` remains a pure local-drift signal.
- A yank or retag of an upstream pattern version is accepted behaviour, not a
  case the tooling defends against — re-pin to a new immutable tag instead.
- We do not add restore-side hash verification or a local content cache. Either
  would only matter if the immutable-tag policy were abandoned; revisit this ADR
  if that ever changes.

See [ADR 4](./0004-vendor-runtime-support-over-submodules.md) for the underlying
decision to vendor runtime support in the first place.

## Amendment (ibek#361)

The Context above describes the vendored files as carrying a
`# Vendored from <source>@<version> — DO NOT EDIT` header. **That header has been
removed.** The decision recorded here — that the upstream tag is the authority
and the lock is a local-drift check only — is unchanged, and is in fact
*strengthened* by the removal:

- Vendored files are now **byte-identical** to the library at its tag, so
  `diff -r <dest>/config/ <library>/<pattern>/` verifies an instance against
  upstream directly. The header made that impossible: every file differed from
  its upstream by one line, so "did this come from the tag?" could only be
  answered through ibek.
- Provenance moves entirely into `runtime-lock.yaml`, which is adjacent,
  committed and authoritative — and was already the only thing anything read.
- Enforcement of *do not edit* moves entirely to `ibek pattern check` via the
  pre-commit hook and `ci_verify.sh`. That raises the stakes on those hooks being
  correct: the file itself carries no "do not edit" warning, so the person
  opening it relies on `check` to catch an edit.

Which files are vendored, and where they land, is now declared per pattern by
`ibek.manifest.yaml` (see
[ADR 5](./0005-pattern-manifest-declares-what-is-vendored.md)); this does not
affect where the authority for their *content* lives.
