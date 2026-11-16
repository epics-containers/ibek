# Files and lifecycle

ibek works in three environments. Command groups are conveniences rather than
strict boundaries: for example, `ioc generate-schema` works outside a container,
while `ioc do-wait` is a runtime command.

| When | Inputs and work | Outputs |
| --- | --- | --- |
| Build or development container | Build modules using ibek-support recipes; link the IOC; collect support definitions | IOC executable, libraries, DB templates, support YAML and an IOC schema |
| Outside containers | Author instance YAML; vendor patterns; combine the image's published schema with local support | Version-controlled configuration, `runtime-lock.yaml`, `ioc.schema.json` |
| Container startup | Validate instance YAML using the installed and instance-local support definitions; render | `st.cmd`, `ioc.subst`, optional PVI and hardware-wait files |

[Build support with Ansible](../how-to/build-support.md) covers module recipes,
dependency order and registration of the files consumed by ibek.

## Schemas describe the inputs

`ibek support generate-schema` produces the schema for **writing support YAML**.
It describes fields such as `entity_models`, `parameters` and `pre_init`.

`ibek ioc generate-schema` reads support YAML and produces the schema for
**writing IOC YAML**. It describes the particular entity types available from
those definitions. Generic IOC releases publish this as `ibek.ioc.schema.json`.
`ibek pattern schema` combines a published image schema with instance-local
support for editor use; see the [vendoring guide](../how-to/vendor-runtime-patterns.md).

Runtime rendering reads the support YAML itself, building Python validation
models from it. It does **not** read the published JSON schema. Keep the selected
image version and editor schema aligned so authoring checks match runtime
capabilities.

## Runtime file flow

```{mermaid}
flowchart LR
    S[Support YAML] --> M[Entity models]
    I[Instance YAML] --> V[Validated entities]
    M --> V
    V --> R[Jinja rendering]
    R --> C[st.cmd]
    R --> U[ioc.subst]
    U --> MSI[EPICS msi]
    T[EPICS DB templates] --> MSI
    MSI --> DB[ioc.db]
    C --> IOC[IOC executable]
    DB --> IOC
```

`runtime generate2` discovers `ioc.yaml` and `runtime.yaml` in the config
folder. Unless explicit definitions are supplied, it searches the image's
`/epics/ibek-defs` and the config folder for support YAML. Additional instance
files can be supplied with `--instance`.

Rendering writes startup commands and database **substitutions**; it does not
compile support or expand those substitutions into `ioc.db`. The image's startup
script coordinates ibek, EPICS `msi`, optional autosave preparation and hardware
waits, then launches the IOC. `runtime place-files` separately copies runtime
protocols and database templates into their search locations.

The main code path is `EntityFactory` → `IocFactory` → `Render` / `RenderDb`.
Entity fields are rendered during validation; startup fragments and database
arguments are rendered when producing the outputs. See the
[Jinja context reference](../reference/jinja-context.md) for ordering and scope,
and the [CLI reference](../reference/cli.md) for command details.
