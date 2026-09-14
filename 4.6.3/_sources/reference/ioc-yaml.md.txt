# IOC instance YAML and schemas reference

This page is a field-by-field reference for an **IOC instance file**
(`*.ibek.ioc.yaml`) and for the three JSON schema artifacts that validate the
ibek YAML files. The audience is IOC-instance designers writing the file that
describes a single IOC.

An IOC instance file lists the *entities* (port drivers, axes, databases, …)
that make up one IOC. ibek loads it into the `IOC` model,
validates every entity against the entity models published by the support
modules baked into the generic-IOC image, and renders the startup assets
(`st.cmd`, database substitutions, etc.).

```{seealso}
- The support-module file that *defines* the entity models is documented in
  {doc}`support-yaml` — this page does not repeat those field tables.
- The Jinja context available inside entity arguments is documented in
  {doc}`jinja-context` — this page does not deep-dive Jinja.
```

## The `$schema` header convention

The first line of an instance file is, by convention, a
[yaml-language-server](https://github.com/redhat-developer/yaml-language-server)
modeline that points an editor at the schema to validate against:

```yaml
# yaml-language-server: $schema=../schemas/motorSim.ibek.ioc.schema.json
```

The comment is not interpreted by ibek itself — it is a hint for editors
(VS Code, Neovim, …) so they offer completion and inline validation while you
type. It should point at one of the *ioc* schemas described in
[Schemas](#schemas) below.

When an instance is managed by `ibek pattern`, the header is rewritten
automatically to point at the self-contained per-instance schema
(`../ioc.schema.json`) every time `ibek pattern schema` runs.

## Top-level keys

The instance file has four top-level keys, defined by the
`IOC` model (`ibek.ioc.IOC`):

| Key           | Type         | Required | Description                                                              |
| ------------- | ------------ | :------: | ------------------------------------------------------------------------ |
| `ioc_name`    | `str`        |   yes    | Name of the IOC instance. May contain Jinja (see below).                 |
| `description` | `str`        |   yes    | Free-text description of what the IOC does.                              |
| `entities`    | `list`       |   yes    | The ordered list of entity instances that make up the IOC.              |
| `shared`      | `Sequence`   |    no    | Scratch space for YAML anchors; ignored by ibek. Defaults to empty.      |

### `ioc_name`

The IOC instance name. Because it is a string field it is Jinja-rendered, so it
is commonly derived rather than hard-coded. Two idioms seen in real instances:

```yaml
# take the name from the yaml file name (without the .ibek.ioc.yaml suffix)
ioc_name: "{{ ioc_yaml_file_name }}"
```

```yaml
# take the name from an environment variable
ioc_name: "{{ _global.get_env('IOC_NAME') }}"
```

### `shared`

`shared` exists only to give you somewhere to declare reusable YAML
[anchors](https://yaml.org/spec/1.2.2/#anchors-and-aliases) that can be aliased
into multiple entities. ibek does not read it — it is dropped after YAML
parsing.

## Entity entries

Each item in `entities` is an entity instance. Every entry has two built-in
fields plus the parameters of its model:

| Field            | Type   | Required | Default | Description                                            |
| ---------------- | ------ | :------: | :-----: | ------------------------------------------------------ |
| `type`           | `str`  |   yes    |    —    | Selects the entity model, written `<module>.<EntityModelName>`. |
| `entity_enabled` | `bool` |    no    | `True`  | Set `false` to keep the entry but skip rendering it.   |

`type` names the support module and the entity model within it, e.g.
`asyn.AsynIP` or `motorSim.simMotorController`. ibek looks up the matching
dynamically-generated subclass of `Entity` (`ibek.ioc.Entity`) and validates the
remaining keys against that model's parameters.

Important validation behaviour:

- **Unknown keys are rejected.** Entity models are validated with
  Pydantic `extra="forbid"`, so a mistyped or unsupported argument is an error
  rather than being silently ignored.
- **Arguments are Jinja-rendered**, including references *between* arguments of
  the same entity. In the sample below `M: M{{ADDR}}` and
  `DESC: Motor {{ADDR}} for ioc {{ioc_name}}` both interpolate other values.
- **Built-in entities** (those whose `type` starts with `ibek.`, such as
  `ibek.repeat`) are provided by ibek itself and subclass
  `BuiltInEntity` (`ibek.ioc.BuiltInEntity`) rather than coming from a support module.

### Worked example

```{literalinclude} ../../tests/samples/iocs/motorSim.ibek.ioc.yaml
:language: yaml
:caption: tests/samples/iocs/motorSim.ibek.ioc.yaml — a simulated-motion IOC instance
```

Rendering this instance produces the startup script below (one of several
generated assets):

```{literalinclude} ../../tests/samples/outputs/motorSim/st.cmd
:language: shell
:caption: tests/samples/outputs/motorSim/st.cmd — generated from the instance above
```

(schemas)=
## Schemas

ibek works with **three** JSON schema artifacts. They differ in scope — what set
of entity models they describe — and in which command produces them.

```{note}
The schema names below are the **current** ones. The old names
`ibek.defs.schema.json` and `<container>.ibek.entities.schema.json` are
**retired** and should not be used or referenced.
```

### 1. The global support schema — `ibek.support.schema.json`

Validates *any* `*.ibek.support.yaml` support-module file (the files that
*define* entity models). It is global: it does not depend on any particular
image or support module. Produce it with:

```bash
ibek support generate-schema [--output FILE]
```

Prints to stdout, or writes to `--output` if given. It is the
`Support.get_schema()` JSON schema of the `Support` model
(`ibek.support.Support`).

::::{dropdown} tests/samples/schemas/ibek.support.schema.json
:icon: code

```{literalinclude} ../../tests/samples/schemas/ibek.support.schema.json
:language: json
```
::::

### 2. The generic-IOC entities schema — `<container>.ibek.ioc.schema.json`

Validates an `*.ibek.ioc.yaml` *instance* file against the entity models
built into a particular generic-IOC image. By convention it is named after the
container, e.g. `motorSim.ibek.ioc.schema.json`. Produce it with:

```bash
ibek ioc generate-schema [DEFINITIONS...] [--output FILE] [--ibek-defs/--no-ibek-defs]
```

- `DEFINITIONS` are paths to one or more `*.ibek.support.yaml` files.
- By default (`--ibek-defs`) the command also adds every support file bundled in
  the image's `IBEK_DEFS` directory, so the schema covers all built-in
  entities.
- The schema is printed to stdout unless `--output` is given.
- `--no-ibek-defs` with **no** `DEFINITIONS` is an error — there would be
  nothing to build a schema from.

This is the schema published as a GitHub release artifact alongside the
generic-IOC image, so instance authors can validate against the exact entity
set their image provides.

::::{dropdown} tests/samples/schemas/motorSim.ibek.ioc.schema.json
:icon: code

```{literalinclude} ../../tests/samples/schemas/motorSim.ibek.ioc.schema.json
:language: json
```
::::

### 3. The per-instance schema — `ioc.schema.json`

A *self-contained* schema for a single IOC instance, named `ioc.schema.json`
(the value of `IOC_SCHEMA_NAME`). It merges schema (2) — fetched as the
published base schema for the image pinned by the instance — with the entity
models from the instance's own vendored / local support files. Produce it with:

```bash
ibek pattern schema [INSTANCE]
```

This writes `ioc.schema.json` at the instance root and rewrites the instance's
`config/ioc.yaml` header to `# yaml-language-server: $schema=../ioc.schema.json`,
so the editor validates against the merged result. See
{doc}`../how-to/vendor-runtime-patterns` for the `ibek pattern` workflow.
