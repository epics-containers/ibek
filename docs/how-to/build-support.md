# Build support with Ansible

ibek-support uses Ansible to turn module recipes into compiled EPICS support and
registered runtime assets. This is the build-time half of
[writing support](write-support.md); `<module>.ibek.support.yaml` describes the
runtime interface separately.

Run these commands in an **epics-containers developer container**, with EPICS,
Ansible, build tools and the generic IOC source already set up. Installing the
ibek Python package alone does not provide this environment. For complete image
setup, follow the
[generic IOC tutorial](https://epics-containers.github.io/main/tutorials/generic_ioc.html).

## Recipe location and build order

The usual layout is:

```text
/epics/generic-source/
  Dockerfile
  ibek-support/
    _ansible/ansible.sh
    motorMotorSim/
      motorMotorSim.install.yml
      motorMotorSim.ibek.support.yaml
  ibek-support-custom/          # optional additional recipe repository
```

`ansible.sh` is the wrapper from `ibek-support/_ansible`, placed on `PATH` by
the container setup. It runs Ansible locally inside the container. It finds a
module in the adjacent `ibek-support*` repositories; the module must occur in
exactly one of them. The shared playbook still comes from `ibek-support`.

Build EPICS dependencies first. Recipes have no dependency-list field or
automatic dependency solver: the generic IOC's Dockerfile supplies the order.
For example, in a developer image with the core support already built:

```bash
ansible.sh motor,motorMotorSim
ansible.sh ioc
```

The comma-separated list builds those modules in order. The separate `ioc`
command generates the combined IOC schema and builds the IOC executable using
the registered libraries and DBDs.

| Command | Work selected |
| --- | --- |
| `ansible.sh motorMotorSim` | One module; prerequisites must already exist. |
| `ansible.sh motor,motorMotorSim` | An explicit ordered list; does not automatically build the IOC afterward. |
| `ansible.sh all` | Modules discovered from `RUN ansible.sh <module>` lines in the generic IOC's Dockerfile, then the IOC. |
| `ansible.sh ioc` | Global support definitions, IOC schema and IOC build. |

`all` reads the Dockerfile as text; it does not execute Dockerfile logic or
infer missing prerequisites. Keep the module build lines simple and ordered.

## Describe a module

A small real recipe, `motorMotorSim/motorMotorSim.install.yml`, is:

```yaml
# yaml-language-server: $schema=../_scripts/support_install_variables.json
module: motorMotorSim
version: R1-3
organization: http://github.com/epics-motor
dbds:
  - motorSimSupport.dbd
  - motorSim.dbd
libs:
  - motorSimSupport
```

`module` and `version` are required. The repository defaults to
`https://github.com/epics-modules/<module>`; `organization` changes its prefix,
or `git_repo` supplies a complete URL. Sources normally live under
`/epics/support/<module>`. List libraries without `lib` prefixes or filename
extensions, and DBDs with `.dbd`.

The module recipe chooses the upstream source version. The generic IOC also
pins an **ibek-support revision**, which chooses the recipes and support YAML.
These are separate version choices.

For Linux package dependencies, use `apt_developer` for packages needed during
compilation and `apt_runtime` for the runtime-image package list. Use
`patch_lines`, `patch_blocks` or `comment_out` for Makefile/configuration edits;
reserve `tasks`, `scripts` and `bash` for work needing more control. The
[recipe reference](../reference/ansible-recipes.md) covers their fields and paths.

## What a build produces

For each module, the playbook installs system dependencies, clones missing
sources, runs custom pre-build tasks, patches configuration, prepares RELEASE
files, builds, records its outputs, runs post-build tasks and registers runtime
assets.

The shared `/epics/support/configure/RELEASE` records module paths. A module's
`configure/RELEASE.local` links to it, so later modules use the dependencies
already built in the container. `remove_macros` adds blank assignments for
unwanted upstream RELEASE macros absent from the shared RELEASE.

| Artifact | Purpose |
| --- | --- |
| `configure/lib_list`, `configure/dbd_list` under `/epics/support` | Libraries and DBDs for linking the IOC. |
| `configure/RELEASE.shell` | Module environment variables and `EPICS_DB_INCLUDE_PATH`. |
| `configure/runtime_debs`, `configure/runtime_files_list` | Inputs for assembling the runtime image. |
| `/epics/ibek-defs/*.ibek.support.yaml` | Links to the module recipe directory's support definitions. |
| `/epics/pvi-defs/*.pvi.device.yaml` | Links to its PVI device definitions. |
| `/epics/autosave/*.req` | Links to its autosave requests. |
| `/epics/support/configure/protocol` | Copies of upstream files selected by `protocol_files`. |

The runtime-registration step handles files directly in the recipe directory,
not a recursive directory tree. `ansible.sh ioc` additionally registers the
shared `_ansible/*.ibek.support.yaml` definitions and writes
`/epics/ibek-defs/ioc.schema.json`. The image build packages these assets; startup
uses ibek to render the instance. See [files and lifecycle](../explanations/architecture.md).

## Rebuild and test a change

After editing a recipe, rebuild its module and then the IOC:

```bash
ansible.sh motorMotorSim -e skip_clean=true
ansible.sh ioc -e skip_clean=true
```

`skip_clean=true` retains intermediate build files after compilation; the
initial `make clean` still runs. `skip_apt=true` skips the entire system step,
including extra downloads and runtime-package registration: use it only when
those steps have already completed and their declarations are unchanged.

An existing source directory is reused without fetching or checking out the
recipe's `version`. The initial `patch_file` also runs only for a new clone.
To test another version, use a fresh developer build or deliberately check out
that revision in the source tree. On a fresh clone the wrapper accepts:

```bash
ansible.sh -v R1-3 motorMotorSim
```

Put `-v VERSION` **before** the module name; later arguments are passed to
`ansible-playbook`. Prefer recording release versions in the recipe for
repeatable image builds. The declared `force_clone` and `force_build` variables
are not implemented switches.

Inspect the registered files and generated schema, then render a small instance
using the module, as in [writing support](write-support.md). Finally run it in
the matching IOC image: compilation and YAML validation do not check hardware
behavior.

When contributing to ibek-support, put the new module in an appropriate
`build-groups.yml` group in dependency order. CI uses the group's base image
and ordered module list. From the ibek-support checkout, check group coverage:

```bash
python3 _scripts/build_matrix.py --check
```

See the [recipe reference](../reference/ansible-recipes.md) for Ansible variables,
build-stage tags and custom task hooks.
