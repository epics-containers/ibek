# Install runtime patterns into an image

A generic IOC image can carry runtime patterns as well as compiled support
modules. Every instance of the image then uses the patterns' entities without
vendoring them, and the image's published `ibek.ioc.schema.json` includes
them. Run `ibek pattern install` in the image's Dockerfile, in the developer
stage, after the last compiled support module is installed and before the step
that builds the image schema (`ibek ioc generate-schema`):

```dockerfile
RUN ibek pattern install \
    ibek-runtime-streamdevice:EdwardsScroll@0.7.3 \
    ibek-runtime-streamdevice:EdwardsNextTurbo@0.7.3
```

To vendor a pattern into one instance instead, see
{doc}`vendor-runtime-patterns`.

## References

Each reference is `library:pattern@version`: both the library and the version
are required, because an image is built from pins and the library names the
support folder the pattern's database files go in. `--list FILE` reads further
references from a file, one per line, with `#` starting a comment. A pattern
may appear only once in a run.

`--source` fetches every pattern from one library location (a git URL or a
local folder) instead of the one its library name resolves to; see
{doc}`../reference/paths-and-environment` for `IBEK_PATTERN_LIBRARIES`. Each git
library is cloned once per version, however many of its patterns are listed.

## Where the files go

The pattern's `ibek.manifest.yaml` selects its files, as for
`ibek pattern add`. Each selected file is installed by its name, where the
image's compiled support modules put theirs:

| Pattern file | Installed to | Found by |
| --- | --- | --- |
| `*.ibek.support.yaml` | `/epics/ibek-defs` | `ioc generate-schema`, `runtime generate2` |
| `*.pvi.device.yaml` | `/epics/pvi-defs` | PVI screen generation |
| `*.proto`, `*.protocol` | `/epics/support/configure/protocol` | the start script, which copies it to the protocol path |
| `*.template`, `*.db`, `*.req` | `/epics/support/<library>/db` | msi's `/epics/support/*/db` include path, autosave's req file search |

A selected file of any other type is refused. The paths follow `EPICS_ROOT`.
`ibek ioc extract-runtime-assets` carries all of them into the runtime image
with its default assets.

## What is refused

Every pattern in a run is fetched and every destination planned before any
file is written. If anything below is found, the install fails and writes
nothing:

- a module that a support YAML in `/epics/ibek-defs`, or an earlier pattern in
  the run, already defines;
- a file that already exists at its destination;
- two patterns, or two files of one pattern, installing the same file;
- a pattern listed twice, or one already recorded in the image lock;
- a pattern that selects no files or no `*.ibek.support.yaml`, or a support
  YAML that declares no `module`;
- a `.template` or `.db` name already in another module's `db/` folder, or
  installed from another library in the same run: msi loads the first match on
  its include path;
- a `.req` name already anywhere under `/epics/support` or in `/epics/autosave`:
  autosave keeps a req file already linked in `/epics/autosave`, and otherwise
  links the first of a name it finds under support.

## The image lock

What a run installs is recorded in `/epics/ibek-defs/runtime-patterns.lock.yaml`:

```yaml
version: 1
patterns:
  EdwardsScroll:
    library: ibek-runtime-streamdevice
    version: 0.7.3
    source: github.com/epics-containers/ibek-runtime-streamdevice
    commit: 4f0c1e2...
    modules:
    - EdwardsScroll
    files:
      ibek-defs/EdwardsScroll.ibek.support.yaml: sha256:...
      support/configure/protocol/EdScroll.proto: sha256:...
      support/ibek-runtime-streamdevice/db/EdwardsScroll.template: sha256:...
```

`commit` is the library commit the version resolved to; it is empty for a local
`--source` folder, which has no pinned commit. `modules` lists the modules the
pattern's support YAML defines, so a tool can tell which modules the image
provides from patterns. File paths are relative to `EPICS_ROOT`.

A later `ibek pattern install` adds its patterns to the lock. The lock is in
`/epics/ibek-defs`, so it reaches the runtime image with the support YAML it
describes. Verify the installed files against it, in either stage:

```bash
ibek pattern check --image
```

## Instances that also vendor a pattern

An instance may vendor a pattern its image already installs. Its
`config/*.ibek.support.yaml` is read after `/epics/ibek-defs`, so its entity
models replace the image's of the same name, and its protocols and templates
are found before the image's. `ibek runtime generate2` warns when the instance
defines a module the image also defines, naming both files. To use the image's
copy, remove the vendored files and the pattern's entry from the instance's
`runtime-lock.yaml`.
