# Select which pattern files an instance vendors

This is an advanced option. Most instances vendor exactly what a pattern's
`ibek.manifest.yaml` lists, as described in
{doc}`vendor-runtime-patterns`; stay with that unless an instance needs a
different set of files.

A **selection** changes the manifest's file-set for one instance only. It can:

- **add** pattern files that the manifest leaves out, such as a simulation
  template in a pattern's `sim/` folder;
- **narrow** the manifest's files, for example to one or two templates from a
  large pattern, by file name or by entity model;
- **place** a selected file at a destination path you choose.

The selection is recorded in the instance's `runtime-lock.yaml`, so `update`,
`restore` and `check` keep the same file-set.

## Add a pattern with a selection

```bash
ibek pattern add ibek-runtime-streamdevice:CryoconM14@0.6.0 services/my-ioc \
    --include 'sim/(.*_sim\.py)=sim/\1' \
    --exclude 'M14_system\.template'
```

`--include SRC=DEST` vendors every pattern file whose path matches the regular
expression `SRC` to `DEST`. `--exclude SRC` stops the manifest from vendoring
files that match `SRC`. Both options can be given more than once.

`SRC` and `DEST` work as they do in the manifest (see the
{doc}`manifest reference <../reference/pattern-manifest>`):

- `SRC` is matched with `re.fullmatch` against the file's path relative to the
  pattern folder.
- A `DEST` whose last part has a file extension is the destination file.
  `SRC` must then match exactly one file. For example,
  `sim/x_sim\.template=config/x.template` places `sim/x_sim.template` at
  `config/x.template`.
- Any other `DEST` is a folder, and the file keeps its path relative to the
  pattern beneath it. For example, `sim/.*=config` places `sim/x.py` at
  `config/sim/x.py`. End `DEST` with `/` to use a folder whose name has an
  extension: `sim/.*=config/sim.d/` places `sim/x.py` at
  `config/sim.d/sim/x.py`.
- A `DEST` containing `\1` or `\g<name>` is the complete destination path,
  built from the regex groups. For example, `sim/(.*)=config/\1` places
  `sim/x.py` at `config/x.py`.

`DEST` is relative to the instance root. ibek splits the argument at its last
`=`, so the regular expression may contain `=`.

The command above records:

```yaml
version: 2
patterns:
  CryoconM14:
    version: 0.6.0
    source: github.com/epics-containers/ibek-runtime-streamdevice
    select:
      include:
      - src: sim/(.*_sim\.py)
        dest: sim/\1
      exclude:
      - M14_system\.template
    files:
      config/CryoconM14.ibek.support.yaml: sha256:...
      config/M14.protocol: sha256:...
      config/M14_sensor.template: sha256:...
      sim/CryoconM14_sim.py: sha256:...
```

## Narrow to named files or models

`--only FILE` vendors only the named pattern files, and `--model NAME` only the
files the named entity models load:

```bash
ibek pattern add ibek-runtime-support:BL21I@0.4.0 services/my-ioc \
    --model TTHBumpstripMonitor
ibek pattern add ibek-runtime-streamdevice:CryoconM14@0.6.0 services/my-ioc \
    --only M14.protocol --only M14_sensor.template
```

- The pattern's `*.ibek.support.yaml` is always vendored, whole and unmodified.
- `--only` takes a path relative to the pattern folder, exactly as it appears
  there. It must be a file the manifest vendors; add any other file with
  `--include`. A name the pattern does not vendor is an error that lists the
  files it does vendor.
- `--model` takes the model's `databases[].file` entries from the support YAML,
  and those of the models it instantiates through `sub_entities`. A database
  file matches the pattern file at that path, or else the one pattern file with
  that base name; a database file that the pattern does not hold comes from the
  image and is not vendored. A database file given as a Jinja expression names
  no single file, so `--model` refuses it; use `--only`.
- `--model` also vendors every protocol file the manifest vendors: each file
  whose name ends in `.proto` or `.protocol`. A pattern with no manifest vendors
  every file, so this is every protocol file in the pattern. StreamDevice
  templates name their protocol inside a record link, not in the support YAML,
  so `--model` cannot tell which protocol a model needs.
- An unknown model is an error that lists the pattern's models.

Both options can be given more than once, and together: ibek vendors the files
of all of them. They cannot be combined with `--exclude`. `--include` works
alongside them, and every file an `include` rule places is vendored.

The first command records:

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

`update` resolves `models` against the release it vendors, so a model whose
template a later release renames still gets the right file. `only` names files
literally: if a later release removes one, `update` fails and writes nothing.
`restore` vendors the same files again.

The support YAML still defines every model of the pattern. An entity whose
model's database files were not vendored fails `ibek runtime generate2`, naming
the model and the `ibek pattern add --model` to re-add it with. `generate2`
checks this when the instance's `runtime-lock.yaml` sits beside its config
folder; it checks only database files given as plain file names, since a path
such as `$(ADCORE)/db/NDStats.template` names a file in the image.

## How files are chosen

ibek considers each file in the pattern folder in this order:

1. It tries the `include` rules in order. The first match decides where the file
   goes, even if the manifest would place the file somewhere else or leave it
   out.
2. If no `include` rule matches, ibek tries the manifest's rules, also in order.
   If a manifest rule matches but an `exclude` regular expression also matches,
   ibek does not vendor the file.
3. ibek does not vendor a file that matches none of the rules.
4. If the selection has `only` or `models`, ibek keeps, of the files the
   manifest placed, the support YAML and the files they name.

To vendor only a few files from a large pattern, `--only` and `--model` are
simplest. Excluding everything and including the files you need also works,
and lets you choose each file's destination:

```bash
ibek pattern add ibek-runtime-streamdevice:CryoconM14@0.6.0 services/my-ioc \
    --exclude '.*' \
    --include 'CryoconM14\.ibek\.support\.yaml=config' \
    --include 'M14\.protocol=config' \
    --include 'M14_sensor\.template=config'
```

Every part of a selection must have an effect. ibek fails, and writes no files,
if any of these is true:

- an `include` rule matches no file;
- an `exclude` expression drops no file that the manifest would vendor;
- after the selection, no files remain to vendor.

The same rule applies on `update`. If a later pattern version renames or removes
a selected file, update the selection in the same change.

The manifest's destination rules also apply to a selection. A
`*.ibek.support.yaml` file must be placed directly under `config/`, and two
files cannot use the same destination. At boot, `ibek runtime place-files` uses
only protocol, database and template files placed directly under `config/`. A
file selected into another folder, such as the simulator above, is vendored and
checked but is not placed in the IOC.

## Change or remove a selection

`add` records the selection given on its command line and replaces any
selection that the pattern already has. Other patterns in the lock keep their
selections and files. To change a selection, run `add` again with the complete
new set of options. To remove it, run `add` with no `--include`, `--exclude`,
`--only` or `--model` options.

ibek removes the pattern's files that are no longer in the file-set. This
includes a file or folder the new file-set needs to replace, such as a folder
at `config/x.template` when the new selection writes a file there. ibek refuses
the change, and writes nothing, if such a file or folder holds anything the
pattern did not vendor.

You can also edit `select:` in `runtime-lock.yaml` and run
`ibek pattern update`. ibek then vendors the files for the edited selection and
removes files that are no longer in the file-set. A lock with a selection must
have `version: 2` or above, and one whose selection has `only` or `models` must
have `version: 4`.

## Lock versions

ibek writes the lowest lock version that can hold the lock's content:

| Version | Adds | Written when |
|---|---|---|
| 1 | `version:` / `patterns:` | no later feature is used |
| 2 | `select.include`, `select.exclude` | any pattern has a selection |
| 3 | top-level `schema_url:` | the lock records a schema URL |
| 4 | `select.only`, `select.models` | any pattern's selection has `only` or `models` |

Each version is the one before plus its keys, so a lock that uses none of a
version's keys reads the same to every ibek that reads the lower version, and
ibek rewrites it byte for byte. An ibek that cannot apply a key refuses the
lock with `unsupported lock version N`. It does not vendor or check a
different file-set from the one recorded. Instances that use a selection need
an ibek that reads its version, including in pre-commit and CI.
