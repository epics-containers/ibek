# `ibek.manifest.yaml` and `runtime-lock.yaml`

The two halves of the on-disk vendoring contract: the **manifest** a pattern
folder may carry in the library (what is vendored, and where), and the **lock**
written at the destination root (what *was* vendored, and its integrity hashes).

For the task recipes see
[Vendor runtime-support patterns](../how-to/vendor-runtime-patterns.md); for the
reasoning see
[ADR 0005](../explanations/decisions/0005-pattern-manifest-declares-what-is-vendored.md).

## `ibek.manifest.yaml`

Lives at the **root of a pattern folder** in a library. Optional — a pattern with
no manifest is vendored through a synthesised default, described below.

```yaml
version: 1
vendor:
  - src: '.*\.(template|proto|protocol|db|req|ibek\.support\.yaml)$'
    dest: config
```

| Key | Meaning |
| --- | --- |
| `version` | Manifest format version. Only `1` is understood; anything else is an error. |
| `vendor` | An **ordered, first-match-wins allow-list** of rules. At least one is required. |
| `vendor[].src` | A regular expression matched against a file's path. |
| `vendor[].dest` | Where the matched file lands, relative to the **destination root**. |

Unknown keys — at the top level or inside an entry — are rejected. That is what
`version:` exists to make survivable: a manifest written for a future ibek fails
loudly rather than being read with half its meaning dropped.

### `src`

Matched with **`re.fullmatch`** against the file's `/`-joined path **relative to
the pattern folder root**. Fullmatch rather than search, so `src: config` cannot
surprise anyone by also matching `myconfig/x.template`.

**Files only.** Directories are never matched, so a rule cannot select a folder;
it selects the files inside it (`src: 'docs/.*'`).

The list is **ordered** and the **first** matching rule wins. A broad rule placed
before a specific one therefore shadows it.

**The manifest is an allow-list**: a file matched by no rule is simply not
vendored. `ibek.manifest.yaml` itself is never vendored, regardless of what
matches it.

### `dest`

Three forms:

- **A plain folder.** Joined with the source's path relative to the pattern root,
  so nesting is preserved: with `dest: config`, `foo/bar.template` lands at
  `config/foo/bar.template`. This is the form a services repo needs, and the only
  one the how-to mentions. A `dest` is a folder when its last part has no file
  extension or when it ends in `/` (`config/db.d/`).
- **A plain file.** A `dest` whose last part has a file extension and does not
  end in `/` (`config/renamed.template`) is the destination path of the one file
  the rule matches. A rule of this form that matches more than one file is
  refused, as two files with one destination.
- **A substitution.** Detected by the presence of a `\1`-style or `\g<name>`
  backreference. The expansion (`match.expand`) produces the **whole**
  destination-relative path, which gives flattening, renaming and re-rooting:

  ```yaml
  vendor:
    - src: '(?:.*/)?(.*\.proto)'
      dest: 'config/\1'          # flatten every .proto into config/
  ```

`dest` is always relative to the **destination root** — the folder you point
`ibek pattern add` at — not to `config/`. `config` is simply the conventional
value for an IOC instance, because that folder is the Kubernetes ConfigMap
payload that reaches the container.

(no-manifest)=

### No manifest

A pattern with no `ibek.manifest.yaml` is vendored through this default
manifest, supplied by `ibek` itself:

```yaml
version: 1
vendor:
  - src: '.*'
    dest: config
```

It is parsed, validated and compiled by the same code as a real manifest, so
there is no second code path and no branch anywhere downstream.

### Validation

The whole manifest is validated, and the complete plan resolved, **before a
single file is written**, so a bad entry cannot leave a half-vendored tree. Every
failure names the offending entry (and, where relevant, the offending file) and
aborts — nothing is skipped with a warning, because a skipped entry means a file
that should be in the IOC silently is not.

| Rejected | Why |
| --- | --- |
| `version:` other than `1` | The manifest means something this ibek does not know. Checked *first*, so a manifest from a future ibek is reported as a future manifest and not as an illegal key. |
| An empty or missing `vendor:` list | A manifest that vendors nothing is a mistake, not a policy. |
| A `vendor:` list that matches **no file** in the pattern | The same mistake, one character further on. Left to run, it prunes every file the pattern had, records `files: {}`, and `check` then passes having verified nothing. |
| An unknown key, anywhere | See `version:` above. |
| A `src` that is not a valid regex | Fails before any destination is resolved. |
| An absolute `dest` | A pattern may only write inside the destination. |
| `..` in `dest` | Checked **after** substitution as well as before, since a capture group can introduce one. |
| A **symlink** anywhere in the pattern folder | Not followed, not vendored, not hashed — including the pattern folder itself, the manifest, and anything inside a folder no rule matches, so one cannot be smuggled in by excluding it. |
| A vendored `*.ibek.support.yaml` outside the `config/` root | `ibek pattern schema` merges `config/*.ibek.support.yaml` non-recursively, so a misrouted one vendors cleanly, checks cleanly, and is then silently missing from the instance's schema. Conditional on the file being vendored at all. |
| Two source files producing the same destination | One would silently overwrite the other, and the lock would record two hashes for the file that survived. Destinations are compared in normal form, so `config/x` and `config/./x` are one destination. |
| One destination inside another (`config/a` and `config/a/b`) | A path cannot be both a file and a folder; discovered during the write it would leave a half-vendored tree. |

```{note}
`ibek runtime place-files` copies `*.proto` / `*.protocol` / `*.db` /
`*.template` into the IOC's runtime search path from the **`config/` root only**.
Nesting those under `config/` is fine for repo organisation and is faithfully
vendored and checked, but they will not be placed at boot.
```

## `runtime-lock.yaml`

Written at the **destination root** (never inside `config/`), and committed.

```yaml
version: 1
patterns:
  lakeshore340:
    version: 1.2.0
    source: github.com/epics-containers/ibek-runtime-streamdevice
    files:
      config/lakeshore340.proto: sha256:...
      config/lakeshore340.ibek.support.yaml: sha256:...
```

| Key | Meaning |
| --- | --- |
| `version` | Lock format version: `1`, or `2` when any pattern has a `select`. ibek writes the lowest version that holds the lock's content. Reading it does not make ibek convert anything on your behalf. |
| `patterns` | Vendored patterns by name, emitted in name order so re-writing the same set produces no diff. |
| `patterns[].version` | The pinned upstream tag. |
| `patterns[].source` | The scheme-stripped library label the pattern came from. |
| `patterns[].select` | Optional. This instance's `include` rules (`src` / `dest`, as in the manifest) and `exclude` regexes applied to the manifest's file-set; see {doc}`../how-to/select-pattern-files`. |
| `patterns[].files` | `<destination-root-relative path>: sha256:<hex>` for every vendored file. |

**Keys are relative to the destination root, always** — `config/x.proto`, not
`x.proto`. The synthesised default (a pattern with no manifest) produces
`config/...` keys naturally, so there is no per-pattern base field and no
branch in `check`.

The recorded digest is over the library's bytes **verbatim**: nothing is injected
or rewritten on the way in, so `check` is a plain `sha256(file) == lock` and
`diff -r <dest>/config/ <library>/<pattern>/` is empty for a clean instance.

A file entry whose value begins with `DIRTY` (conventionally
`DIRTY # <reason>`) is a sanctioned, visible divergence: `check` warns rather
than fails, without needing `--allow-dirty`.

```{warning}
`ibek` reads and writes exactly the `version:` / `patterns:` shape above, and
refuses any other top-level key.
`add`, `update` and `check` all refuse a `runtime-lock.yaml` in any other
shape, with a generic message naming a conversion script — see
{ref}`the vendoring how-to <unrecognised-locks>`.
```
