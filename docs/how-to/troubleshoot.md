# Troubleshoot ibek

## An entity or argument is rejected

Check the `type: module.Entity` against the support definitions used for that
run. `runtime generate2` discovers definitions in the image and config folder
unless `--definitions` was supplied, which replaces discovery. IOC schemas
are specific to their support definitions: a schema from another image may
accept entities the running image cannot supply. See
{doc}`../reference/ioc-yaml` and {doc}`../reference/support-yaml`.

For rendering failures, check parameter spelling, definition order, and the
available {doc}`../reference/jinja-context`. Missing environment variables
fail when accessed directly through `env`; use `env.get("NAME", "default")`
when a default is intentional.

## No schema download, or an old schema appears

A cached base schema is revalidated on every run and is also used when the
server cannot be reached, including across fresh virtual environments. A
`Using cached schema ... could not revalidate it` message means the download
failed but the cache hid the failure. Run with a new `IBEK_SCHEMA_CACHE`
directory to reproduce a first download; the complete recipe and cache key are
in {doc}`../reference/paths-and-environment`.

If the command reports that schema generation was skipped, check the image
in `values.yaml` or `compose.yml` / `compose.yaml`, its explicit tag, and the
repository's `ibek.ioc.schema.json` release asset. A skip leaves an existing
schema untouched and exits 0.

If the command exits 1 with `Cannot refresh ... ioc.schema.json`, ibek could not
reach the server and has no cached copy for the image tag. Check network access
and TLS certificates. A malformed cached JSON file raises a parsing error; using
a fresh cache also isolates that case.

## Runtime protocols or templates are missing

Put instance `.proto`, `.protocol`, `.db`, and `.template` files directly in
`config/`. Run `runtime place-files` after `runtime generate2`, because
generation clears its output directory. Confirm the image startup script's
search paths include `/epics/runtime/protocol` and `/epics/runtime/db` as
appropriate. Generated `ioc.subst` still needs expansion by EPICS `msi` before
the IOC loads the database.

## A vendored pattern fails its integrity check

Inspect the reported file and `runtime-lock.yaml`. `ibek pattern restore`
replaces local edits from the recorded source; `update` records a newly
selected version. Use deliberate `DIRTY` entries only when the divergence
should be visible in version control. See {doc}`vendor-runtime-patterns`.

## Generation works but the IOC fails to start

Inspect `st.cmd` and `ioc.subst` under `/epics/runtime`, then the IOC's output.
Successful rendering validates ibek inputs; it does not prove that an EPICS
command, database template, shared library, or hardware endpoint is available.
For image building, deployment, and operational debugging, use the
[epics-containers documentation](https://epics-containers.github.io/).

## Changing an Ansible recipe's version did not change the sources

The clone step reuses an existing `/epics/support/<module>` checkout without
fetching or switching revisions. Changing `version` or passing `ansible.sh -v`
only selects a revision for a new clone; the declared `force_clone` variable
does not implement a refresh. Check the existing checkout's Git revision and
local changes. Use a fresh developer build to test the recipe from scratch,
or deliberately switch the source checkout after preserving local work.
See [rebuilding support](build-support.md).

## A module builds but its entities are not recognised

Compilation and support-definition registration are separate steps. Confirm
the recipe directory contains a top-level `*.ibek.support.yaml` file and that
its link under `/epics/ibek-defs` resolves to the intended file. A build limited
to `--tags do_build` skips runtime registration; rerun the full module recipe,
then `ansible.sh ioc` to regenerate the combined schema.

At runtime, check that the selected image contains that definition. Explicit
`runtime generate2 --definitions` arguments replace automatic discovery and
must include all required files. If only editor completion is wrong, refresh
the schema used by the editor; the local build schema and an image's published
release schema are separate artifacts. See [building support](build-support.md)
and [schema caching](../reference/paths-and-environment.md).

## A dependency's RELEASE path is wrong

Inspect `/epics/support/configure/RELEASE` and the affected module's
`configure/RELEASE.local` link. The link should target the shared RELEASE;
the dependency's macro should point to its actual source directory. Check
the dependency recipe's `macro` and `local_path`, and build it before its
consumer. Recipes do not resolve dependency order automatically.

Also inspect applicable architecture-specific `configure/RELEASE.*` files:
upstream paths can override the container's paths. The current role includes
`RELEASE.local` last in the supported RELEASE files. After correcting the
recipe or checkout, rerun the dependency and consumer builds rather than
maintaining a separate hand-edited RELEASE configuration. See the
[recipe reference](../reference/ansible-recipes.md).
