# Support YAML

A `*.ibek.support.yaml` file defines the entity types that IOC configurations
can instantiate. It describes parameters, startup commands and database
instances; it does not build the underlying EPICS support module.

```yaml
module: example
entity_models:
  - name: Device
    description: A device with a configurable prefix
    parameters:
      name:
        type: id
        description: Unique device name
      P:
        type: str
        description: PV prefix
      count:
        type: int
        description: Number of channels
        default: 4
    post_defines:
      label:
        description: Label for startup diagnostics
        value: "{{ name }} ({{ count }} channels)"
    pre_init:
      - type: comment
        value: "Configure {{ label }}"
    databases:
      - file: example.db
        args:
          P:
          N: "{{ count }}"
```

This publishes `example.Device`. The database file must be available in the
IOC's database search path. See [IOC YAML](ioc-yaml.md) for instantiation and
[Jinja context](jinja-context.md) for evaluation rules.

## File and entity fields

At the top level, `module` and `entity_models` are required. Optional `shared`
is a list in which to declare reusable YAML anchors; it does not create Jinja
variables. The same `shared` field is available within each entity model.
Unknown fields are rejected.

Each `entity_models` entry accepts:

| Field | Meaning |
| --- | --- |
| `name`, `description` | Required type name and explanation. The published type is `<module>.<name>`. |
| `parameters` | Named inputs, each with a `type`, `description` and optional `default`. |
| `pre_defines` | Named calculated values evaluated before parameters. |
| `post_defines` | Named calculated values evaluated after parameters. |
| `pre_init`, `post_init` | Lists of startup snippets before or after `iocInit`. |
| `databases` | Database templates and macro arguments. |
| `env_vars` | Environment assignments emitted into the startup script. |
| `sub_entities` | Additional entity instances created for each instance of this model. |
| `pvi` | Optional PVI device, interface and UI settings. |
| `shared` | YAML anchors for reuse within this file. |

All fields except `name` and `description` are optional; collections default to
empty and `pvi` defaults to null.

## Parameters and calculated values

A parameter without a non-null `default` is required in IOC YAML. Defaults for
numeric, boolean and collection parameters can be native YAML values or Jinja
expressions containing `{{ ... }}`.

| Parameter `type` | Meaning |
| --- | --- |
| `str` | String, optionally containing Jinja. |
| `int`, `float`, `bool` | Typed scalar or an expression producing it. |
| `list`, `dict` | YAML collection or an expression producing one. |
| `id` | Unique identifier by which other entities refer to this instance. |
| `object` | Reference to an already declared entity's ID. |
| `enum` | A label selected from a required `values` mapping. |

Use one `id` parameter per entity model. Duplicate IDs are errors. For an
`object` parameter called `controller`, `{{ controller }}` gives the target's
ID and `{{ controller.P }}` reads its `P` field.

Enum inputs use the **keys** of `values`; output templates receive their
associated values. A null value retains the key itself:

```yaml
mode:
  type: enum
  description: Operating mode
  default: automatic
  values:
    automatic: 0
    manual: 1
    diagnostic:
```

Currently, enum conversion applies only to top-level entities. Entities created
by repeats or sub-entities retain the selected label rather than its mapped value.

Defines have required `description` and `value` fields, and optional `type`
(default `str`; also `int`, `float`, `bool`, `list`). They are calculated by the
support model, not supplied by the IOC author. Within each group, declaration
order matters: put dependencies first. Use `post_defines` for calculations
that require fully rendered parameters.

## Startup snippets and environment assignments

`pre_init` and `post_init` contain snippets with `value` (default empty),
`type` (`text` by default, or `comment`) and `when` (`every` by default).
Comments get `# ` on each line. Jinja is evaluated against the owning entity.

```yaml
pre_init:
  - when: first
    value: |
      # Commands needed once for this entity model
      exampleSetup()
  - value: 'exampleConfigure("{{ name }}", {{ count }})'
post_init:
  - value: 'dbpf("{{ P }}Enable", "1")'
```

Use `every` or `first`; `last` is not implemented. `first` tracks the model name
and snippet kind (`text`/`comment`), shared across pre- and post-init sections.
Group commands that must run once into one snippet: separate `first` text
snippets for the same model suppress one another.

`env_vars` entries require `name` and `value`; both accept Jinja. They generate
`epicsEnvSet` commands before the pre-init snippets. Include IOC-shell quoting
in the values when needed:

```yaml
env_vars:
  - name: DEVICE_PREFIX
    value: '"{{ P }}"'
```

These commands set the **IOC's** environment when its startup script runs.
To read the environment of the **ibek process while generating files**, use
{ref}`env <environment-variables>`.

## Databases

Each entry requires `file` (a template filename, optionally Jinja) and `args`
(a mapping of EPICS macro names to Jinja strings). A blank argument passes the
same-named entity field or shared Jinja variable through:

```yaml
databases:
  - file: example.db
    enabled: "{{ count > 0 }}"
    args:
      P:                       # Equivalent to "{{ P }}"
      N: "{{ count }}"
      DESC: "Device {{ name }}"
```

`enabled` defaults to `"True"`. Rendered `true`, `yes` or `1` (case insensitive)
enables the entry; other values disable it. Use `args: {}` for no macros;
`args: null` is not supported by rendering.

Argument keys containing `*` or `?` are interpreted as Python regular
expressions matched against entity field names, not shell wildcards. For
example, `"M.*":` passes matching fields through. Prefer explicit arguments
when the set is small. Entries for the same rendered filename are grouped
into a substitution table, so keep their argument names and order consistent.

## Sub-entities

A model can compose existing entity types:

```yaml
sub_entities:
  - type: example.Device
    name: "{{ name }}_child"
    P: "{{ P }}CHILD:"
    count: 1
```

Each entry supplies `type`, optional `entity_enabled` (default true), and the
child's parameters. Those parameters are first rendered in the parent's
context and then validated against the child model. Children are inserted
immediately after the parent; nesting and `ibek.repeat` are supported. An
object passed through this intermediate context can be a serialized mapping:
use explicit fields such as `{{ controller.name }}` rather than relying on
`{{ controller }}` to produce an ID.

## PVI

| Field | Meaning and default |
| --- | --- |
| `yaml_path` | Required device YAML path, absolute or relative to `PVI_DEFS`; accepts Jinja. |
| `ui_index` | Add this instance to the IOC UI index; default true. |
| `ui_macros` | Macro mapping for the UI and generated database, with the same blank-value convention as database arguments; default null. Supply a mapping (or `{}`) when `ui_index` or `pv` is enabled. |
| `pv` | Generate a database exposing the PVI device structure over PVAccess; default false. |
| `pv_prefix` | Prefix for the generated PVI PV, e.g. `$(P)`; default empty. |

An identically named device YAML file in the instance's `config/` overrides
the installed definition, including parent definitions. Runtime generation
can disable PVI output with `--no-pvi`.

## Schema

Generate the support-file schema with:

```bash
ibek support generate-schema --output ibek.support.schema.json
```

Point your editor at that file using a first-line comment:

```yaml
# yaml-language-server: $schema=../schemas/ibek.support.schema.json
```

This schema validates support definitions. An IOC schema is generated from a
specific set of those definitions; see {ref}`IOC YAML schemas <schemas>`.
