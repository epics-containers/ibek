# CLI reference

Use `ibek --help` and `ibek <group> <command> --help` for the installed
version. The complete command reference below is generated from the CLI.

## When to run each command

| Phase | Commands | Purpose |
| --- | --- | --- |
| Container build | `support generate-schema`, `support apt-install-runtime-packages` | Describe support YAML and install declared runtime Debian packages. |
| Container build | `ioc generate-schema`, `ioc extract-runtime-assets` | Describe the image's available entities and package its runtime files. |
| Container startup | `runtime generate2`, `runtime place-files`, `runtime generate-autosave`, `ioc do-wait` | Generate the instance, place its files, prepare autosave, and wait for hardware. |
| Container build | `dev stamp` | Record the source tree the image is built from. |
| Development container | `dev status`, `dev sync` | Compare the container with the mounted project and bring it level. |
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

### A container from a pre-built image

A devcontainer mounts the host project over `/epics/generic-source`, the
folder the image was built from. The host's checkout can differ from the
image's copy, so the last step of the Dockerfile's developer stage records
what was built:

```dockerfile
COPY Dockerfile requirements.txt ${SOURCE_FOLDER}/
RUN ibek dev stamp
```

`dev stamp` writes `/epics/dev-stamp.json`: hashes of the Dockerfile's `ARG`
and `FROM` lines, `requirements.txt`, `ibek-support/_ansible` (without its
`vars` folder), and for each `RUN ansible.sh <module>` line the module's
folder in `ibek-support*`, split into its definition files
(`*.ibek.support.yaml`, `*.pvi.device.yaml`, `*.req`) and the rest. A third
hash per module covers what its `install.yml` says to clone: `module`,
`version`, `organization`, `git_repo`, `recursive`, `patch_file` and the
content of the patch. The hashes cover file names and content, with CRLF read
as LF. They leave out file modes and a fixed list of names: `.git`,
`.ansible`, `__pycache__`, `*.pyc`, `*build.log`, `*~`, `*.swp` and
`.DS_Store`. Any other file in a hashed folder counts, tracked by git or not.

```bash
ibek dev status          # show the differences, change nothing
ibek dev sync            # fix what needs no build, report the rest
ibek dev sync --build    # also rebuild what is out of date
```

| Difference | `dev sync` | `dev sync --build` |
| --- | --- | --- |
| A module's definition files | Runs `ansible.sh <modules> --tags runtime`, removes dangling links from `/epics/ibek-defs`, `/epics/pvi-defs` and `/epics/autosave`, regenerates `/epics/ibek-defs/ioc.schema.json`. | The same. |
| A module's other files, the module list, `_ansible` | Reported. | Runs `ansible.sh <module>` for the first such module and each one after it in the Dockerfile, then `ansible.sh ioc`. |
| `requirements.txt` | Reported. | Runs `uv pip install --upgrade -r requirements.txt`, regenerates the schema and stops: run it again for anything more. |
| The base image | Reported: pull a newer developer image or rebuild it locally. | The same. |
| The IOC binary is missing, older than `ioc/Makefile` or a file in `ioc/configure` or `ioc/iocApp` (`O.*` folders apart), or older than the start of the last build by `dev sync --build` | Reported: run `make` in `/epics/ioc`. | Runs `ansible.sh ioc`. |

A module is built from the source already in `/epics/support/<module>`,
unless what its `install.yml` says to clone has changed. Then
`ansible.sh <module> --tags clone -e force_clone=true` first removes that
folder and clones it again: **edits made in the folder are discarded**. Both
`dev status` and `dev sync` name each folder that `dev sync --build` would
remove. The new clone is recorded before the build, so if the build fails,
the next `dev sync --build` builds the folder as it then is, without cloning
again. A module with no folder in `/epics/support` is cloned by its build. A
module the Dockerfile no longer builds stays installed, and reported, until
the container is recreated from an image built without it.

The IOC line goes when the IOC binary is newer than each of the files and
the build it is compared with, as it is once `make` has built it.

`dev sync` exits 0 when it only has differences to report; a command it runs
that fails gives its exit code. The stamp records each module as it is built,
so after a failed build the next `dev sync --build` starts at the module that
failed. In an image with no stamp, each of these commands says so in one line
and exits 0. A stamp that cannot be read is one line too: `dev status` and
`dev sync` exit 0, `dev sync --build` exits 1. `dev instance` prints the same
report after linking the instance, and a note when the instance's image tag
differs from `ioc-version` in `/epics/versions.json`.

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
