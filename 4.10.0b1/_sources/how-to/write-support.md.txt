# Write support for a module

[ibek-support](https://github.com/epics-containers/ibek-support) connects EPICS
modules to generic IOC images. Its module directories hold two different kinds
of configuration:

| File | Used by | Purpose |
| --- | --- | --- |
| `<module>.install.yml` | ibek-support's Ansible build tooling | Source version, dependencies, libraries, DBDs and build customizations |
| `<module>.ibek.support.yaml` | ibek | Entity models available to IOC instances |
| Optional patches, protocols, PVI definitions and autosave requests | Build or startup tooling | Supporting assets |

Current recipes use `ansible.sh <module>` in the EPICS build/development
container. Older images and instructions may instead use `install.sh` scripts
calling `ibek support` helpers. `ansible.sh` belongs to ibek-support, not the ibek
Python CLI. Recipe Jinja is evaluated by Ansible, separately from ibek's runtime
Jinja context.

For recipes, dependencies, rebuilding and asset registration, see
[Build support with Ansible](build-support.md) and the
[recipe reference](../reference/ansible-recipes.md).

## Expose the runtime interface

Start with a small entity model for one useful feature: a port, a controller or
a database instance. Declare the inputs in `parameters`; emit setup commands in
`pre_init`, commands that require a running IOC in `post_init`, and database
loads in `databases`. Use `id` parameters and `object` references when entities
need to refer to each other.

The [render tutorial](../tutorials/build-an-ioc.md) gives a complete minimal
example. The [support YAML reference](../reference/support-yaml.md) covers
parameter types, ordering, shared values and compound entities; the
[Jinja reference](../reference/jinja-context.md) explains how expressions resolve.

Test definitions locally before rebuilding an image:

```bash
ibek ioc generate-schema mymodule.ibek.support.yaml \
    --no-ibek-defs --output ioc.schema.json
IOC=/epics/ioc RUNTIME_DIR=/epics/runtime ibek runtime generate2 config \
    --definitions mymodule.ibek.support.yaml --no-pvi --output generated
```

Repeat `--definitions` for each required support file. Explicit definitions
replace automatic runtime discovery, so include every module the instance uses.
Inspect both `st.cmd` and `ioc.subst`; successful rendering does not prove that
the driver commands or EPICS macro names are correct. Test the resulting IOC in
its developer container as well.

## Include support in an image

The generic IOC project selects ibek-support and the modules to build. The
Ansible recipes build the modules and register their support YAML under
`/epics/ibek-defs`, with PVI and autosave files in their corresponding locations.
`ibek ioc generate-schema` can then discover the installed definitions and
produce the schema published with the image. At startup, ibek reads those same
definitions to interpret instance YAML.

For the complete image build/test workflow, follow
[the generic IOC tutorial](https://epics-containers.github.io/main/tutorials/generic_ioc.html)
and [editing a support module](https://epics-containers.github.io/main/tutorials/support_module.html).
If the change only needs runtime YAML, DB templates or protocols and its compiled
support is already in the image, consider a
[runtime pattern](vendor-runtime-patterns.md) instead.
