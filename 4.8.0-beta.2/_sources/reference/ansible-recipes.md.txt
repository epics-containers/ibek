# Ansible build recipes

An ibek-support recipe is `<module>/<module>.install.yml`, loaded as Ansible
variables by `ansible.sh`. It builds EPICS support; it is separate from the
`*.ibek.support.yaml` consumed by ibek at runtime. See
[build support modules](../how-to/build-support.md) for the workflow.

The tables below describe the current
[ibek-support roles](https://github.com/epics-containers/ibek-support/tree/main/_ansible),
including behavior that differs from its editor schema. These defaults belong
to ibek-support, so use the version selected by your generic IOC project.

## Source and build fields

| Field | Default and behavior |
| --- | --- |
| `module` | Required, nonempty module name. Usually matches the recipe directory. |
| `version` | Required, nonempty Git tag, branch or commit used for the initial clone. Quote version numbers. |
| `organization` | `https://github.com/epics-modules`. |
| `git_repo` | `{{ organization.rstrip('/') }}/{{ module }}`; override for a different repository. |
| `local_path` | `{{ support_folder }}/{{ module }}`, normally `/epics/support/<module>`. |
| `recursive` | False if unset; enable Git submodule checkout. |
| `make_options` | `-j{{ ansible_processor_vcpus }}`; passed to `make`. |
| `macro` | Uppercase module name with hyphens replaced by underscores; the module's RELEASE macro. |
| `remove_macros` | Empty list; add blank assignments for macros absent from the global RELEASE file. Existing assignments are retained. |
| `extra_release_macros` | Empty mapping; add or replace global RELEASE assignments, e.g. `AREA_DETECTOR: "$(SUPPORT)"`. |
| `libs` | Empty list; library names, without `lib` prefix or extension, added to `configure/lib_list` for IOC linking. |
| `dbds` | Empty list; DBD filenames, including `.dbd`, added to `configure/dbd_list`. |
| `skip_clean` | False; true skips the final `make clean`, **not** the initial clean before compilation. |

An existing `local_path` is used as-is: it is not fetched, checked out at
`version`, or reset. `patch_file` also runs only on a fresh clone. The declared
`force_clone` and `force_build` variables currently have no implementing tasks;
they do not change that behavior.

## Dependencies and runtime assets

All lists below default to empty.

| Field | Behavior |
| --- | --- |
| `apt_developer` | Install Linux build packages. Names use the package manager; absolute paths identify local `.deb` files. |
| `apt_runtime` | Record Linux runtime packages in `configure/runtime_debs` for the image's runtime stage; does not install them here. |
| `download_extras` | List of `{url: ..., dest: ...}` downloads, performed before package installation. |
| `runtime_files` | Absolute paths recorded in `configure/runtime_files_list` for later runtime extraction. |
| `protocol_files` | Paths relative to `local_path`, copied into `/epics/support/configure/protocol`. |

`skip_apt: true` skips the whole system-dependency stage, including downloads
and registration of `apt_runtime`, not just package installation. It defaults
to false. Downloads otherwise run for either target architecture; package
installation and runtime-package registration are restricted to Linux targets.

Support YAML, PVI definitions and autosave requests need no list entries:
the role links top-level `*.ibek.support.yaml`, `*.pvi.device.yaml` and `*.req`
from the recipe directory into `/epics/ibek-defs`, `/epics/pvi-defs` and
`/epics/autosave` respectively. These are files from the **recipe directory**,
whereas `protocol_files` come from the **module source directory**.

## Customization fields

The following fields are lists, except `patch_file`, which is one mapping.
Paths in `comment_out`, `patch_lines`, `patch_blocks`, and
`remove_files_prebuild` are relative to `local_path`. Script, task and patch
file paths are relative to `ibek_support_folder`, the recipe directory.

| Field | Entry format and behavior |
| --- | --- |
| `remove_files_prebuild` | List of paths to delete before the build; default empty. |
| `comment_out` | `{path, regexp, when?}`; prefixes matching, not-already-commented lines with `# `. Pre-build only. |
| `patch_lines` | `{path, regexp, line, when?, post_build?}`; replace a matching line or append when absent; creates missing files. |
| `patch_blocks` | `{path, block, insertafter?, marker?, when?, post_build?}`; insert or update a managed text block; creates missing files. |
| `patch_file` | `{path, when, commit?}`; apply a Git patch on a fresh clone when enabled. See below. |
| `scripts` | `{path, post_build?}`; execute `bash <recipe-dir>/<path>` with `local_path` as working directory. |
| `bash` | `{cmd, when?, post_build?}`; execute a command with `/bin/bash` in `local_path`. |
| `tasks` | `{path, when?, post_build?}`; include a file containing an Ansible task list. |

Omitted list fields are empty. `post_build` defaults to false. For entries that
support `when`, omission normally means true; `patch_file` is the exception
and is disabled unless its `when` is true. Supply evaluated conditions:

```yaml
patch_lines:
  - path: configure/CONFIG_SITE
    regexp: '^WITH_FEATURE\s*='
    line: WITH_FEATURE = YES
    when: "{{ is_linux }}"
bash:
  - cmd: ./prepare-generated-sources.sh
    when: "{{ is_linux }}"
tasks:
  - path: extra-build-steps.yml
    post_build: true
```

Do not use `when: is_linux` as a variable reference: it is a literal string in
these recipe structures. `scripts` does **not** implement `when`; use a `bash`
entry or conditional Ansible task when needed.

For `patch_blocks`, `insertafter` defaults to `EOF` and `marker` to
`# {mark} ANSIBLE MANAGED BLOCK`. Use distinct markers for multiple pre-build
blocks in one file. Post-build blocks currently ignore a custom marker and
always use that default.

For `patch_file`, enable it explicitly and supply a base commit when needed:

```yaml
patch_file:
  path: fix-build.patch
  commit: "0123456789abcdef0123456789abcdef01234567"  # Replace with the base commit
  when: "{{ is_rtems | bool }}"
```

An enabled patch causes a full initial clone rather than a shallow one. If a
`commit` is supplied, the role checks it out before `git apply`. A recipe that
omits `commit` applies to the configured `version`; the schema's advertised
`HEAD` default is not injected into the recipe by the playbook.

## Task order

For each module, the role performs:

1. System packages/downloads, then source clone and optional Git patch.
2. Custom pre-build `tasks`.
3. File removals, comments, line/block patches, `scripts`, then `bash` commands.
4. RELEASE setup, including linking `configure/RELEASE.local` to the global
   RELEASE and ensuring it is included last in applicable RELEASE files.
5. `make clean`, `make {{ make_options }}`, then the optional final clean.
6. Registration of module paths, library/DBD lists and runtime files; post-build
   line/block patches, scripts and bash commands.
7. Custom post-build `tasks`, then links/copies for runtime assets.

Tasks within a customization list run in list order. Across lists, role order
wins: a pre-build `tasks` entry runs before `patch_lines`, regardless of their
order in the recipe. These are build instructions with real side effects,
including shell execution; run them in the intended build/development container.

The support-stage tags, in order, are `system`, `clone`, `pre_build_tasks`,
`pre_build`, `release`, `do_build`, `post_build`, `post_build_tasks`, and `runtime`.
For an already prepared module, `ansible.sh motorMotorSim --tags do_build`
runs the compilation stage. A tagged run still performs the `always`-tagged
module discovery and variable loading, and assumes skipped prerequisites have
already been completed. Use a full module build to test a recipe change.

## Build-time Jinja context

Recipe expressions are evaluated by **Ansible**, not ibek's runtime renderer.
They have Ansible variables, facts, lookups and filters; they do not gain ibek's
`env` mapping, `_global` helpers or IOC entity parameters.

| Variable | Meaning |
| --- | --- |
| `module`, `version`, `local_path`, `macro` | The selected module's recipe values and defaults. |
| `all_root` | Root containing the generic IOC Dockerfile and `ibek-support*` checkouts; normally two directories above the playbook. |
| `ibek_support_root`, `ansible_root` | Main `ibek-support` checkout and its `_ansible` directory. |
| `ibek_support_folder` | Discovered recipe directory, possibly in an additional `ibek-support*` checkout. |
| `epics_folder`, `support_folder` | `/epics` and `/epics/support`. |
| `configure_folder`, `release_file` | Shared support `configure` directory and its global `RELEASE`. |
| `target_arch`, `host_arch` | Environment values `EPICS_TARGET_ARCH` and `EPICS_HOST_ARCH`. |
| `is_linux`, `is_rtems` | Whether the target architecture contains `linux` or `RTEMS`, respectively. |
| `config_linux_host` | `configure/CONFIG_SITE.linux-x86_64.Common`. |
| `config_linux_target` | `configure/CONFIG_SITE.Common.linux-x86_64`. |
| `ansible_processor_vcpus` | Gathered CPU fact used in the default parallel build options. |

Read other environment variables through an Ansible lookup, for example
`"{{ lookup('ansible.builtin.env', 'MY_BUILD_SETTING') }}"`.
The two `config_linux_*` paths are fixed strings, not derived from `host_arch`.

## Editor schema and runtime behavior

The repository's `_scripts/support_install_variables.json` is generated by
`_scripts/install_schema.py`. It assists editing but the playbook loads YAML
as variables; it does not instantiate that Python model or apply its defaults.

The schema currently differs from the roles: it omits `skip_clean` and
`skip_apt`, does not describe every templated condition, and describes the
`macro` default without hyphen replacement. Some optional `when` defaults
also differ. For execution, use the behavior documented above and the selected
checkout's role variables/tasks; the schema is not an execution contract.
