# CLI reference

Complete reference for the `ibek` command-line interface. Everything below is
generated directly from the Typer application, so it always matches the
installed version.

`ibek` groups its commands by the lifecycle phase in which you run them:

- **`ibek support`** — runs during the **Generic IOC container build**, while
  EPICS support modules are being compiled and configured.
- **`ibek ioc`** — runs during the **container build** to turn the installed
  support definitions into a schema and to package the runtime assets.
- **`ibek runtime`** — runs at **container start-up**, turning an IOC
  instance's YAML into the boot script and databases it runs from.
- **`ibek dev`** — runs **inside a development container** to wire a checked-out
  instance or support module into the EPICS tree for live editing.
- **`ibek pattern`** — runs in a **services repository** to vendor pinned
  runtime-support patterns into an IOC instance and verify their integrity.

```{note}
This page is reference material. `ibek <group> <command> --help` is the
authoritative, version-exact source of truth for any command — if the text here
and `--help` ever disagree, trust `--help`.
```

For the YAML formats these commands consume and produce, and for the vendoring
concepts behind `ibek pattern`, see the dedicated pages — they are not repeated
here:

- {doc}`support-yaml` and {doc}`ioc-yaml` — the support and instance YAML
  formats and the schema artifacts.
- {doc}`jinja-context` — the Jinja template context used during generation.
- {doc}`../how-to/vendor-runtime-patterns` — how to use `ibek pattern`.

## Things worth knowing

```{note}
**`ibek runtime generate` is LEGACY.** It builds a startup script from a single
instance file and is superseded by `ibek runtime generate2`, which supports
multiple instance files. `generate2` auto-gathers `ioc.yaml` and `runtime.yaml`
from its positional config-folder argument (e.g. a `ioc.yaml` from the image
plus a `runtime.yaml` from the services repo), and `--instance`/`-i` supplies
any further instance files on top of those. Prefer `generate2` for new work.
```

```{note}
**`ibek support generate-schema --output` has no default.** If you omit
`--output`, the global JSON schema is printed to stdout; pass `--output FILE` to
write it to a file instead. The same is true of `ibek ioc generate-schema`.
```

```{note}
**`ibek pattern check` integrity policy.** By default a hash mismatch between a
vendored file and `runtime-lock.yaml` is a hard error (non-zero exit). Pass
`--allow-dirty`, or set the environment variable `IBEK_ALLOW_DIRTY=1`, to
downgrade mismatches to warnings while still reporting them.
```

## Command tree

```{eval-rst}
.. typer:: ibek.__main__:cli
   :prog: ibek
   :show-nested:
   :make-sections:
   :width: 80
```
