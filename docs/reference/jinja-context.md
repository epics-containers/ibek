# Jinja template context reference

Every string value in a support YAML file — `pre_init`/`post_init` text,
`databases` argument values, `env_vars` values, and parameter/`pre_defines`/
`post_defines` defaults — is treated as a [Jinja2](https://jinja.palletsprojects.com/)
template. This page enumerates **everything you can reference inside those
templates** when writing a support YAML file.

For the meaning of each parameter or define *type*, see
[](support-yaml.md); this page only covers what is in scope at render time and
how a declared type drives coercion.

## The render entrypoint

Every per-entity string field goes through a single method, `Utils.render`,
which compiles the string with `jinja2.StrictUndefined`. (The top-level assembly
templates `st.cmd.jinja` and `ioc.subst.jinja` are rendered separately and
directly via `Template(...).render()` in `gen_scripts.py`, not through
`Utils.render`.) For the per-entity renders the practical consequences are:

- **Unknown names raise.** Referencing a name that is not in scope is an error,
  not an empty string. The original Jinja exception is re-wrapped and raised as
  a `ValueError` that quotes the offending template text, so a typo in a
  variable name fails the `ibek` run rather than producing silent garbage.
- **No custom Jinja extensions are registered.** ibek does **not** add any
  custom filters, globals or tests. Only stock Jinja2 builtins are available
  (e.g. `range`, `format`, `sort`, `list`, `int`, `dict`, slicing and
  arithmetic), plus the `_global` helper object described below. If a filter or
  function is not part of standard Jinja2, it is not available here.

A single `Utils` instance (the `UTILS` singleton) is shared across **one whole
`ibek` generate run**, so any state it accumulates (counters, stored variables)
persists from one entity to the next in render order.

## Top-level names

### The entity's own fields

Inside a template for a given entity, **all of that entity's fields are
available as bare names**:

- every declared **parameter**,
- every **`pre_defines`** value,
- every **`post_defines`** value,
- the always-present `type` (the entity model name, e.g.
  `motorSim.simMotorController`) and `entity_enabled` (a bool, default `True`).

Fields become available in a fixed order — **`pre_defines` → `parameters` →
`post_defines`** — and each is rendered in that order. A later field may
reference an earlier one, but not the other way round. For example, in the
`motorSim.simMotorAxis` model the `start` parameter defaults to another
parameter's value:

```yaml
start:
  type: str # int or jinja string
  description: The starting position of the axis (in counts)
  default: "{{home}}"
```

Here `home` (declared earlier) is in scope when `start`'s default is rendered.

### `_global` — the shared `Utils` object

The name `_global` is bound to the shared `UTILS` singleton in every template.
Its state survives across the whole generate run, which is what makes counters
and stored variables useful. Its public methods are:

| Call | Returns | Notes |
| --- | --- | --- |
| `_global.get_env(key)` | `str` | The environment variable `key`, or `''` if it is unset. Never raises. |
| `_global.set(key, value)` | `value` | Stores `value` under `key` **and returns it**, so it can be used inline (the assignment and the rendered output happen in one expression). |
| `_global.get(key, default='')` | stored value | Reads a variable previously stored with `set`; returns `default` if unset. |
| `_global.incrementor(name, start=0, increment=1, stop=None)` | `int` | A named counter. First call creates it set to `start`; each later call adds `increment`. Raises `ValueError` if the value would exceed `stop`, or if a variable of that name already exists and is not an `int`. |

The `render` and `render_map` methods are also reachable on `_global` but are
mostly internal. One `render_map` behaviour is worth knowing because it shapes
how `databases` args are written: **a value of `None` means "use the key name as
the template"**, i.e. `{'P': None}` is equivalent to `{'P': '{{ P }}'}`. This is
why a `databases` arg can be left blank to pass the matching parameter straight
through:

```yaml
databases:
  - file: sim_motor.db
    args:
      controllerName:   # == controllerName: "{{ controllerName }}"
      P:
      DESC:
```

### Variables created with `set`/`incrementor` are also bare names

Whenever you call `_global.set(...)` or `_global.incrementor(...)`, the stored
variable is **also spread into the template context as a bare top-level name**
for all subsequent renders. So after a `post_defines` stores a value with
`set`, a later `pre_init` line can read it directly by name. From
`tests/samples/support/utils.ibek.support.yaml`:

```yaml
post_defines:
  test_global_var:
    description: test global variable setter
    value: '{{  _global.set("magic_global", 42) }}'
  get_global:
    description: test global variable getter
    value: '{{  _global.get("magic_global") }}'

pre_init:
  - type: comment
    value: global "magic" is {{ get_global }}
  - type: comment
    value: counter "InterruptVector" is now {{ _global.incrementor("InterruptVector", start=192, stop=255) }}
```

Here `get_global` (a `post_defines` field) is referenced as a bare name in
`pre_init`. The same counter name reused in a different entity continues from
where it left off, because `UTILS` is shared across the run.

### Special variables

Two extra names are injected into every template:

| Name | Value |
| --- | --- |
| `ioc_yaml_file_name` | The stem (filename without extension) of the **first** IOC instance YAML file being processed. |
| `ioc_name` | The IOC instance name, **already rendered** (its own `{{ }}` expressions have been expanded before it is offered to other templates). |

## Type coercion

Jinja always produces a string. ibek coerces that string back to a typed value
in two ways:

1. **Declared types coerce automatically.** When a parameter or define is
   declared as `int`, `float`, `bool`, `list` or `dict`, the rendered string is
   passed through `ast.literal_eval` and cast to that type. (Types `str`,
   `object`, `id` and `enum` are not coerced — they stay as the rendered
   string, with `object`/`id` then resolved as described below.) Note that
   `pre_defines`/`post_defines` support only `str`, `float`, `int`, `bool` and
   `list`; the `dict`, `object`, `id` and `enum` types are parameter-only.
2. **Inline coercion suffix.** You can force coercion inside a single
   expression by ending it with a `| <typ> }}` suffix, where `<typ>` is one of
   `int`, `float`, `bool`, `list`, `dict`. This is a genuine **Jinja builtin
   filter** that Jinja itself applies during rendering — ibek does **not** strip
   it. After rendering, ibek separately inspects the template text with a regular
   expression (`re_get_type`) and, if the suffix names one of those five types,
   applies the same `ast.literal_eval`-based cast to the result.

```{warning}
Because the suffix is a real Jinja filter, it only works for filter names Jinja
actually knows. Writing a suffix that is **not** a Jinja filter (e.g.
`{{ x | foo }}`) makes Jinja raise *"No filter named 'foo'"*, which ibek
re-wraps as a `ValueError`. A suffix that *is* a real Jinja filter but not one of
the five coercion types (e.g. `| upper`) is applied by Jinja and then ignored by
ibek's coercion step, so no extra cast happens.
```

## Referencing another entity

A parameter declared with `type: object` does not hold a string — after
validation it holds the **actual referenced `Entity`**. Two things follow:

- **Rendering the object itself** (`{{ port }}`) calls `Entity.__str__`, which
  returns the value of the target entity's `id` field. This **raises** if the
  referenced entity has no `id`-typed parameter.
- **Attribute access** (`{{ port.field }}`) reaches into the target entity's
  fields.

From `motorSim.simMotorAxis`, the `controller` parameter is an object reference
to a `simMotorController`:

```yaml
databases:
  - file: basic_asyn_motor.db
    args:
      P: "{{controller.P}}"     # the controller's P field
      PORT: "{{controller}}"    # the controller's id (its controllerName)
```

```{note}
In `sub_entities`/`shared` anchors there is no type information, so an object
parameter there is just a plain dict. As the `quadEM.Plugins` model notes, you
must use an explicit field such as `{{DEVICE.P}}` / `{{DEVICE.PORT}}` rather than
`{{DEVICE}}` in that context.
```

## The JinjaString rule for non-string defaults

A default for an `int`, `float`, `bool`, `list` or `dict` **parameter** may be
written as a string, **but only if that string actually contains a `{{ ... }}`
expression**. This is enforced by schema validation against the `JINJA` pattern
(`.*\{\{.*\}\}.*`). A bare literal string in one of these slots is rejected — use
the native YAML literal instead (e.g. `default: 20`, not `default: "20"`). The
rule applies only to typed parameter defaults; a `pre_defines`/`post_defines`
`value` is typed `Any` with no pattern and is not subject to it.

To include literal `{{` / `}}` characters that Jinja should **not** evaluate,
wrap them in `{% raw %} ... {% endraw %}`, as the `simMotorController.DESC`
default does:

```yaml
DESC:
  type: str
  default: "Simulated Motion Controller testing escaping: {% raw %} {{enclosed in escaped curly braces}} {% endraw %}"
```

## The `st.cmd` (phase 2) render

The boot script is rendered in a second pass from `st.cmd.jinja`. That
top-level render sees:

- `_global` (the same shared `UTILS` singleton), and
- every variable spread from `UTILS.variables` (everything created with
  `set`/`incrementor`),
- plus the **already-rendered per-entity blocks**: the environment-variable
  entries, the pre-`iocInit` script entries, and the post-`iocInit` entries.

Because the per-entity blocks are already rendered before this pass, counters
and stored globals reflect the totals accumulated across all entities by the
time the `st.cmd` template runs.
