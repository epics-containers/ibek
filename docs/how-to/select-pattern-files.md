# Select which pattern files an instance vendors

This is an advanced option. Most instances vendor exactly what a pattern's
`ibek.manifest.yaml` lists, as described in
{doc}`vendor-runtime-patterns`; stay with that unless an instance needs a
different set of files.

A **selection** changes the manifest's file-set for one instance only. It can:

- **add** pattern files that the manifest leaves out, such as a simulation
  template in a pattern's `sim/` folder;
- **narrow** the manifest's files, for example to one or two templates from a
  large pattern;
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
- A plain folder `DEST` keeps that relative path beneath the folder. For
  example, `sim/.*=config` places `sim/x.py` at `config/sim/x.py`.
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

## How files are chosen

ibek considers each file in the pattern folder in this order:

1. It tries the `include` rules in order. The first match decides where the file
   goes, even if the manifest would place the file somewhere else or leave it
   out.
2. If no `include` rule matches, ibek tries the manifest's rules, also in order.
   If a manifest rule matches but an `exclude` regular expression also matches,
   ibek does not vendor the file.
3. ibek does not vendor a file that matches none of the rules.

To vendor only a few files from a large pattern, exclude everything and include
the files you need:

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
selection that the pattern already has. To change a selection, run `add` again
with the complete new set of options. To remove it, run `add` with no
`--include` or `--exclude` options. ibek removes files that are no longer in the
file-set.

You can also edit `select:` in `runtime-lock.yaml` and run
`ibek pattern update`. ibek then vendors the files for the edited selection and
removes files that are no longer in the file-set. A lock with a selection must
have `version: 2`.

## Lock versions

ibek writes `version: 1` when no pattern in the lock has a selection, and
`version: 2` when any pattern has one. A lock without a selection therefore
stays readable by every ibek that reads version 1. An ibek that cannot apply a
selection refuses a version 2 lock with `unsupported lock version 2`. It does
not vendor or check a different file-set from the one recorded. Instances that
use a selection need an ibek that reads version 2, including in pre-commit and
CI.
