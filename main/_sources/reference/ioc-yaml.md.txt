# IOC YAML

An IOC configuration lists the entities to instantiate from the available
[support definitions](support-yaml.md). It selects and configures compiled
support; adding an entity does not install a missing driver.

```yaml
# yaml-language-server: $schema=../ioc.schema.json
ioc_name: "{{ env.get('IOC_NAME', 'demo') }}"
description: Example device IOC
entities:
  - type: example.Device
    name: device1
    P: "DEMO:"
    count: 4
```

This uses the `example.Device` model in the support reference. For real
configurations, use the types offered by your image's schema.

## Fields and ordering

| Field | Meaning |
| --- | --- |
| `ioc_name` | Required string; Jinja is evaluated before the entities. |
| `description` | Required description. |
| `entities` | Required ordered list of entity instances. |
| `shared` | Optional list for YAML anchors; does not create Jinja variables. |

Every entity supplies `type: <module>.<model>` and the parameters declared by
that model. Parameters with defaults may be omitted. Unknown fields, missing
required parameters, invalid enum labels and duplicate IDs are errors.

An `object` parameter refers to another entity's `id` value. Put the target
before the referring entity. Parameter expressions can read earlier rendered
parameters, for example `DESC: "Axis {{ ADDR }}"`; their evaluation order comes
from the **support definition**, not the order of keys in the IOC file.
See [Jinja context](jinja-context.md).

`entity_enabled: false` suppresses an ordinary entity's startup snippets and
databases, but the entity is still validated and its IDs and calculated values
are processed. It does not recursively disable sub-entities, PVI generation or
built-in wait entries. Remove those entries when they should not be generated.

## Reuse with YAML anchors

Anchors are YAML's own mechanism, resolved before ibek evaluates Jinja. Use
`shared` to hold common parameter maps:

```yaml
shared:
  - &common
    P: "DEMO:"
    count: 4
entities:
  - type: example.Device
    <<: *common
    name: device1
```

## Repeating entities

`ibek.repeat` expands one entity for each item in `values`. Set `variable` to
the iteration name (default `index`). `<variable>_num` is the zero-based
position, independent of the item's value.

```yaml
entities:
  - type: ibek.repeat
    variable: channel
    values: [A, B, C]
    entity:
      type: example.Device
      name: "device_{{ channel }}"
      P: "DEMO:{{ channel }}:"
      count: 1
```

`values` can also be `"{{ range(1, 5) | list }}"`. Repeats may nest; use distinct
variable names to retain access to outer values. Support models can use the
same mechanism within `sub_entities`.

Expansion happens after the top-level entities have been loaded. References
between repeated entities work when the target is expanded first; a regular
top-level entity cannot refer to an ID that only a later expansion creates.

## Waiting for hardware

```yaml
entities:
  - type: ibek.wait_ip
    device: controller
    address: "192.168.0.10:4000"
    timeout: 30
```

Generation writes an entry to `wait_list.yaml` without waiting. The image's
startup script runs `ibek ioc do-wait` to process the list.
`address` is required, `device` defaults to
`DEVICE`, and `timeout` defaults to zero (wait indefinitely). `ibek.wait_usb`
accepts `id: "vendor_id:product_id"` with the same optional fields, but its
runtime implementation is not yet available.

## Multiple files

`ibek runtime generate2` accepts `config/ioc.yaml` and optional
`config/runtime.yaml`, plus explicit `--instance` files. Each is a complete IOC
YAML document with `ioc_name`, `description` and `entities`; their entity lists
are concatenated. Use the same `ioc_name` in all files: the main IOC retains
the first document's name, while later loads update the Jinja `ioc_name`.
The [CLI reference](cli.md) describes file discovery and explicit ordering.

(schemas)=
## Schemas

The first-line `yaml-language-server` comment enables editor validation and
completion. It is an editor hint, not a runtime instruction. Runtime validation
uses the supplied support definitions.

| Schema | Describes | Command |
| --- | --- | --- |
| `ibek.support.schema.json` | Support YAML structure | `ibek support generate-schema` |
| `<image>.ibek.ioc.schema.json` | IOC entities available in a particular image | `ibek ioc generate-schema` |
| `ioc.schema.json` | Image entities plus an instance's local/vendored definitions | `ibek pattern schema` |

Generate an IOC schema directly from support files:

```bash
ibek ioc generate-schema --no-ibek-defs \
  example.ibek.support.yaml --output example.ibek.ioc.schema.json
```

Without `--no-ibek-defs`, this command also includes the image's installed
support definitions from `/epics/ibek-defs` (under `EPICS_ROOT`). The resulting
schema includes ibek's built-in entities.

For a managed instance, run `ibek pattern schema INSTANCE`. It merges the
image's published schema with local definitions, writes `ioc.schema.json`, and
updates the `config/ioc.yaml` editor hint. See
[runtime patterns](../how-to/vendor-runtime-patterns.md) for version selection,
caching and reproducible schema downloads.
