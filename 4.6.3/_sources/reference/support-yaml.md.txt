# Support module YAML reference (`*.ibek.support.yaml`)

A `*.ibek.support.yaml` file is authored by **support-module developers**. It
declares the set of *Entity Models* that a support module publishes — i.e. the
things an IOC instance is allowed to instantiate from that module (a motor
controller, an asyn port, a database, and so on). This is the developer-facing
half of ibek; the instance-facing half (the IOC's `ioc.yaml`) is covered in
[](ioc-yaml.md).

## File header convention

Every support file should begin with the language-server schema hint so editors
can offer completion and validation:

```yaml
# yaml-language-server: $schema=https://github.com/epics-containers/ibek/releases/download/<version>/ibek.support.schema.json
```

In the tested samples the hint points at a locally generated copy, e.g.
`$schema=../schemas/ibek.support.schema.json`. The global schema is produced by:

```bash
ibek support generate-schema
```

(See [](cli.md) for the full command surface.)

### Model configuration that applies everywhere

All models in this file are Pydantic models that inherit
`globals.BaseSettings` (`src/ibek/globals.py:128-134`), which sets:

- `extra="forbid"` — **unknown keys are rejected**. A typo in a field name is an
  error, not a silently ignored value.
- `use_enum_values=True` — enum fields deserialize to their underlying value.

The **one exception** is [`SubEntity`](#subentity), which is declared with
`extra="allow"` (`src/ibek/sub_entity.py:4`) so it can carry arbitrary
pass-through parameters.

## Top-level `Support` keys

Source: `src/ibek/support.py:17-30`.

| Key             | Type                      | Required | Default | Meaning                                                                 |
| --------------- | ------------------------- | -------- | ------- | ----------------------------------------------------------------------- |
| `module`        | `str`                     | **yes**  | —       | Support module name, normally the repo name.                            |
| `entity_models` | `Sequence[EntityModel]`   | **yes**  | —       | The Entity Models an IOC can create using this module.                  |
| `shared`        | `Sequence[Any]`           | no       | `()`    | Scratch space to hold YAML anchors for re-use; ibek does not read it.   |

## `EntityModel` keys

Source: `src/ibek/entity_model.py:124-174`. Each entry under `entity_models`
describes one class of Entity, published to IOC instances as the type
`<module>.<name>`.

| Key            | Type                              | Required | Default | Meaning                                                                        |
| -------------- | --------------------------------- | -------- | ------- | ------------------------------------------------------------------------------ |
| `name`         | `str`                             | **yes**  | —       | Published as the Entity type `<module>.<name>`.                                |
| `description`  | `str`                             | **yes**  | —       | Human description of the Entity.                                               |
| `pre_defines`  | `dict[str, Define]`               | no       | `{}`    | Calculated values rendered with Jinja **before** parameters.                   |
| `parameters`   | `dict[str, Param]`                | no       | `{}`    | The arguments an IOC instance supplies (discriminated by `type`, see below).   |
| `post_defines` | `dict[str, Define]`               | no       | `{}`    | Calculated values rendered with Jinja **after** parameters.                    |
| `pre_init`     | `Script`                          | no       | `()`    | Startup-script snippets emitted before `iocInit()`.                            |
| `post_init`    | `Script`                          | no       | `()`    | Startup-script snippets emitted after `iocInit()` (e.g. `dbpf`).               |
| `databases`    | `Sequence[Database]`              | no       | `[]`    | Database templates to load.                                                    |
| `env_vars`     | `Sequence[EnvironmentVariable]`   | no       | `()`    | Environment variables to set in the boot script.                              |
| `pvi`          | `EntityPVI \| None`               | no       | `None`  | PVI device definition for this Entity.                                         |
| `sub_entities` | `Sequence[SubEntity]`             | no       | `()`    | Other Entities instantiated for each instance of this model.                   |
| `shared`       | `Sequence[Any]`                   | no       | `()`    | YAML-anchor scratch space (as in `Support.shared`).                            |

### Render order: `pre_defines` -> `parameters` -> `post_defines`

These three groups are rendered in this strict order
(`src/ibek/ioc.py:91-105`). The practical consequences:

- a `parameter` **default** can refer to a `pre_define` (the pre_define already
  has a value);
- a `post_define` can refer to a `parameter` (the parameter is already
  resolved);
- a `pre_define` cannot read a `parameter` or `post_define`, and a `parameter`
  cannot read a `post_define`.

Deep Jinja semantics (the available context, filters, escaping) live in
[](jinja-context.md).

## Parameter types

`parameters` is a discriminated union keyed by `type`
(`src/ibek/entity_model.py:118-121`, classes in `src/ibek/parameters.py:47-126`).
Every parameter also takes a required `description`. The `default` field is
optional throughout; when omitted the IOC instance **must** supply the value.

| `type`   | `default` accepts                       | Notes                                                                                                      |
| -------- | --------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `str`    | `str \| None`                           | Plain string (may contain Jinja).                                                                          |
| `int`    | `int` or `JinjaString`                  | A Jinja string is allowed so the default can be computed.                                                  |
| `float`  | `float` or `JinjaString`                | As `int`.                                                                                                  |
| `bool`   | `bool` or `JinjaString`                 | As `int`.                                                                                                  |
| `dict`   | `dict` or `JinjaString`                 | YAML map, or a Jinja string rendering to one (e.g. `... \| dict`).                                         |
| `list`   | `list` or `JinjaString`                 | YAML list, or a Jinja string rendering to one (e.g. `... \| list`).                                        |
| `object` | `str` (an id) or `object`               | A **reference to another Entity** by its id; resolved to the actual Entity during validation.             |
| `id`     | `str`                                   | **Registers a unique global id** for this Entity; other Entities' `object` params can point at it.        |
| `enum`   | any of the `values`                     | **Requires** a `values` map (see below).                                                                   |

A `JinjaString` is just a `str` constrained to contain `{{ ... }}`
(`src/ibek/parameters.py:14-16`).

### `object` and `id` semantics

- **`id`** — when the IOC sets this parameter, the value is added to a global id
  index. A duplicate id raises `ValueError: Duplicate id ...`
  (`src/ibek/ioc.py:72-76`). At most one parameter per model is the id field.
- **`object`** — the IOC supplies the id string of another Entity. During whole-
  model validation ibek looks that id up and replaces the string with the actual
  Entity instance (`src/ibek/ioc.py:59-62`), so Jinja can then reach into its
  fields (e.g. `{{ controller.P }}`).

### `enum` `values`

`EnumParam` requires a `values` mapping of **label -> value**
(`src/ibek/parameters.py:101-109`). The generated schema offers the *labels* to
the IOC author (`src/ibek/entity_factory.py:139-143`), while ibek substitutes
the corresponding *value* at render time
(`IocFactory.fixup_enums`, `src/ibek/ioc_factory.py:57`). Example:

```yaml
DIR:
  type: enum
  description: The direction of the axis
  default: 0
  values:
    Pos: 0
    Neg: 1
```

## `Define` model (values for `pre_defines` / `post_defines`)

Source: `src/ibek/parameters.py:35-44`.

| Key           | Type         | Required | Default | Meaning                                                       |
| ------------- | ------------ | -------- | ------- | ------------------------------------------------------------- |
| `description` | `str`        | **yes**  | —       | What the calculated value is for.                             |
| `value`       | `Any`        | **yes**  | —       | The contents: a literal or a Jinja expression.                |
| `type`        | `DefineType` | no       | `str`   | One of `str` / `float` / `int` / `bool` / `list`.             |

`DefineType` values are `str`, `float`, `int`, `bool`, `list`
(`src/ibek/parameters.py:19-27`).

## `Database`

Source: `src/ibek/entity_model.py:34-53`.

| Key       | Type                            | Required | Default  | Meaning                                                                                  |
| --------- | ------------------------------- | -------- | -------- | ---------------------------------------------------------------------------------------- |
| `file`    | `str`                           | **yes**  | —        | Filename of the database template under `<module_root>/db`.                              |
| `enabled` | `str`                           | no       | `"True"` | A Jinja string that renders to `False` disables loading this database.                   |
| `args`    | `Mapping[str, str \| None] \| None` | **yes** | —     | Args passed through to the database. The key is required (it has no default), but you may pass `args: null` or `args: {}`. A `None` value for an individual entry means `ARG: '{{ ARG }}'` (pass through the same-named Entity arg). |

In the sample, `enabled: "{{not is_cs}}"` selects one of two database templates
per axis, and the bare `M:` / `ADDR:` args take their values from the like-named
parameters.

## `EnvironmentVariable`

Source: `src/ibek/entity_model.py:56-62`.

| Key     | Type  | Required | Meaning                                  |
| ------- | ----- | -------- | ---------------------------------------- |
| `name`  | `str` | **yes**  | Name of the environment variable (Jinja).|
| `value` | `str` | **yes**  | Value to set (Jinja).                    |

## `Script` (for `pre_init` / `post_init`)

A `Script` is a sequence of `Text` or `Comment` snippets
(`src/ibek/entity_model.py:65-88`), discriminated by `type`.

### `Text` (`type: text`, the default)

| Key     | Type  | Required | Default   | Meaning                                          |
| ------- | ----- | -------- | --------- | ------------------------------------------------ |
| `type`  | `"text"` | no    | `text`    | Discriminator.                                   |
| `when`  | `str` | no       | `"every"` | **Free string**; `first` renders once per model. |
| `value` | `str` | no       | `""`      | Raw text added to the startup script.            |

### `Comment` (`type: comment`)

| Key     | Type   | Required | Default | Meaning                                                  |
| ------- | ------ | -------- | ------- | -------------------------------------------------------- |
| `type`  | `"comment"` | no  | —       | Discriminator (required to select this variant).        |
| `when`  | `When` | no       | `every` | The `When` enum: `first` / `every` / `last`.             |
| `value` | `str`  | no       | `""`    | Comment text; every line is prefixed with `# `.          |

```{warning}
Two foot-guns in the script model:

- **`when: last` is not implemented.** It raises
  `NotImplementedError("When.last not yet implemented")` at render time
  (`src/ibek/render.py:45-46`). Only `first` and `every` work.
- **`Text.when` is a free `str` while `Comment.when` is the `When` enum.** This
  inconsistency means `Text` will silently accept an invalid `when` value where
  `Comment` would reject it. Stick to `first` / `every`.
```

## `EntityPVI`

Source: `src/ibek/entity_model.py:91-115`.

| Key         | Type                       | Required | Default | Meaning                                                                      |
| ----------- | -------------------------- | -------- | ------- | ---------------------------------------------------------------------------- |
| `yaml_path` | `str`                      | **yes**  | —       | Path to the `.pvi.device.yaml`, absolute or relative to `PVI_DEFS`.          |
| `ui_index`  | `bool`                     | no       | `True`  | Whether to add the UI to the IOC index.                                      |
| `ui_macros` | `dict[str, str \| None] \| None` | no | `None`  | Macros to launch the UI; each key must be an arg of the owning Entity.       |
| `pv`        | `bool`                     | no       | `False` | Whether to generate a PVI PV (a PVAccess PV describing the device structure).|
| `pv_prefix` | `str`                      | no       | `""`    | PV prefix for the PVI PV, e.g. `$(P)`.                                        |

(subentity)=

## `SubEntity`

Source: `src/ibek/sub_entity.py`. This is the **only** model with
`extra="allow"`: beyond the two declared fields it accepts arbitrary keys, which
are passed through as parameters to the instantiated sub-Entity.

| Key              | Type   | Required | Default | Meaning                                                            |
| ---------------- | ------ | -------- | ------- | ----------------------------------------------------------------- |
| `type`           | `str`  | **yes**  | —       | The Entity type to instantiate (`<module>.<name>`).               |
| `entity_enabled` | `bool` | no       | `True`  | Enable or disable this sub-Entity instance.                       |
| *(any other key)*| —      | no       | —       | Pass-through parameter forwarded to the sub-Entity.               |

## Worked example

The following file is part of the ibek test suite and exercises most of the
schema: id/object references, `str`/`int`/`float`/`bool`/`enum` parameters, enum
values, Jinja defaults, conditional databases, scripts and PVI. (It does not
demonstrate `dict`/`list` parameters, `pre_defines`/`post_defines`, `env_vars`,
`sub_entities` or `Comment` snippets.)

```{literalinclude} ../../tests/samples/support/motorSim.ibek.support.yaml
:language: yaml
:caption: tests/samples/support/motorSim.ibek.support.yaml — a complete, tested support module
```

## Annotated skeleton

```yaml
# yaml-language-server: $schema=.../ibek.support.schema.json
module: myModule                 # REQUIRED: support module / repo name
entity_models:                   # REQUIRED: one or more Entity Models
  - name: myThing                # REQUIRED: published as myModule.myThing
    description: What it makes    # REQUIRED
    pre_defines:                 # rendered first
      base: { description: prefix, value: "{{ P }}", type: str }
    parameters:                  # what the IOC supplies
      name: { type: id, description: unique name }
      P:    { type: str, description: PV prefix }
      port: { type: object, description: ref to another entity by id }
      mode: { type: enum, description: mode, default: a, values: { a: 0, b: 1 } }
    post_defines:                # rendered last; may read parameters
      full: { description: full pv, value: "{{ P }}:{{ name }}" }
    pre_init:
      - value: "someIocShellFunction({{ name }})"   # Text, when: every
    databases:
      - file: my.db
        enabled: "True"
        args:
          P:                     # None => pass through the same-named arg
    env_vars:
      - { name: MY_VAR, value: "{{ P }}" }
    pvi:
      yaml_path: my.pvi.device.yaml
    sub_entities:
      - type: myModule.other     # extra keys below are pass-through params
        someParam: "{{ P }}"
```
