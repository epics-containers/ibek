# CLI reference

Use `ibek --help` and `ibek <group> <command> --help` for the installed
version. The complete command reference below is generated from the CLI.

## When to run each command

| Phase | Commands | Purpose |
| --- | --- | --- |
| Container build | `support generate-schema`, `support apt-install-runtime-packages` | Describe support YAML and install declared runtime Debian packages. |
| Container build | `ioc generate-schema`, `ioc extract-runtime-assets` | Describe the image's available entities and package its runtime files. |
| Container startup | `runtime generate2`, `runtime place-files`, `runtime generate-autosave`, `ioc do-wait` | Generate the instance, place its files, prepare autosave, and wait for hardware. |
| Development container | `dev instance`, `ioc build-docker` | Select a checked-out instance; experimentally execute Dockerfile steps. |
| Outside the IOC container | `pattern add/update/check/restore/schema` | Maintain runtime support and editor schemas in an instance repository. |

These are intended environments, not enforced modes. Schema generation can also
run outside a container with explicit input paths. Compiling EPICS modules is
handled by the build recipes in [ibek-support](https://github.com/epics-containers/ibek-support),
not by a general-purpose `ibek build` command.

## Runtime generation

In an IOC image, the startup script normally runs the equivalent of:

```bash
ibek runtime generate2 /epics/ioc/config
ibek runtime place-files /epics/ioc/config
ibek runtime generate-autosave
ibek ioc do-wait
```

`generate2` reads `ioc.yaml` then `runtime.yaml` when present in the supplied
folder. Repeated `--instance` / `-i` options add files **before** those two;
the first file supplies the IOC name and later files append entities. Without
`--definitions`, support definitions are discovered recursively in
`$EPICS_ROOT/ibek-defs` and the config folder. Supplying `--definitions` replaces
that automatic discovery; repeat it for each required file.

Generation recreates the output directory (default `/epics/runtime`), writing
`st.cmd`, `ioc.subst`, and any generated auxiliary files. Run `place-files`
**after** generation: it copies top-level `.proto` / `.protocol` files into
`runtime/protocol`, and `.db` / `.template` files into `runtime/db`.

PVI generation is enabled by default; `--no-pvi` disables it. `--output` changes
the startup/substitution output directory, but does not relocate every runtime
or PVI path. See {doc}`paths-and-environment`.

The image's startup script still expands substitutions with EPICS `msi` and
launches the IOC executable. `generate2` does not start the IOC.
`runtime generate` remains available for legacy single-file invocations; use
`generate2` for new scripts.

## Schema generation

The three schema commands have different inputs:

```bash
# The format accepted by every *.ibek.support.yaml file
ibek support generate-schema --output ibek.support.schema.json

# IOC entities supplied by explicitly named support definitions
ibek ioc generate-schema --no-ibek-defs motor.ibek.support.yaml \
    --output ibek.ioc.schema.json

# Published image entities plus an instance's local runtime support
ibek pattern schema services/my-ioc
```

The first two print JSON to stdout when `--output` is omitted.
`ioc generate-schema` includes definitions directly in `/epics/ibek-defs` by
default; `--no-ibek-defs` disables that lookup. `pattern schema` instead uses
the published schema for the instance's image; see
{doc}`../how-to/vendor-runtime-patterns` and {doc}`paths-and-environment` for
its cache behavior.

## Development commands

```bash
ibek dev instance /workspaces/my-services/services/my-ioc
```

This replaces `/epics/ioc/config` with a symlink to the instance's `config`
directory. It removes the previous directory or link, so use it in the
development container with the instance configuration kept in version control.

`dev support` is a placeholder and raises `NotImplementedError`.
`ioc build-docker` is experimental: it interprets supported Dockerfile steps
inside the development container; it is not a substitute for building an image.
`ioc extract-runtime-assets` moves files out of its source tree for speed;
run it only in the disposable packaging stage intended by the image build.

## Complete command reference

```{eval-rst}
.. typer:: ibek.__main__:cli
   :prog: ibek
   :show-nested:
   :make-sections:
   :width: 80
```
