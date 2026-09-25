# Jinja rendering and context

ibek uses Jinja to turn IOC parameters and support definitions into startup
commands and database substitutions. Jinja runs **during generation**;
EPICS `$(MACRO)` expressions belong to the later database/IOC processing stages.

```yaml
databases:
  - file: example.db
    args:
      P: "{{ P }}"               # ibek substitutes the entity parameter
      PORT: "{{ controller }}"   # ibek substitutes the referenced entity ID
      HOST: "$(DEVICE_HOST)"     # left for EPICS macro expansion
```

ibek does not run Jinja over the contents of every `.db` file. It renders the
filename and argument values into `ioc.subst`; EPICS tooling expands the
referenced database templates.

## Evaluation order

1. Render the IOC's `ioc_name`.
2. Load top-level entities in order. For each entity, render `pre_defines`,
   `parameters`, then `post_defines`, in each group's declaration order.
3. Expand repeats and sub-entities, rendering child inputs in their parent or
   iteration context before validating the child.
4. Generate PVI output when enabled, render the startup environment assignments,
   pre-init and post-init snippets, then render database substitutions.

Use earlier values as dependencies. Parameter fields exist before their
individual render, so an early expression can see a later parameter's **raw**
value; it cannot rely on that value already having been expanded. Use
`post_defines` for calculations requiring resolved parameters. Enum labels are
mapped to their output values after top-level entity validation, so defines
should not depend on that conversion having happened yet.

Jinja expressions are evaluated where supported, not recursively over every
YAML node. In particular, native list/dict parameter contents and `shared`
anchor storage are not generally traversed and rendered. Return a whole typed
collection from an expression when it needs calculation.

## Names in an entity template

| Name | Value |
| --- | --- |
| Parameter and define names | This entity's fields, with defines added as they are evaluated. |
| `type`, `entity_enabled` | Entity type and enable flag. |
| `ioc_name` | Rendered IOC name. |
| `ioc_yaml_file_name` | Stem of the first input filename: `ioc.yaml` gives `ioc`; `demo.ibek.ioc.yaml` gives `demo.ibek.ioc`. |
| `env` | Read-only view of the process environment. |
| `_global` | Shared helper object described below. |
| Names stored by `_global.set` or `incrementor` | Shared values available to subsequent renders. |

Object references expose the target entity's attributes: `{{ controller.P }}`.
Rendering the object itself, `{{ controller }}`, produces its ID. IDs must
already exist when references are resolved.

Shared helper variables take precedence over entity fields of the same name.
The special IOC names and `_global` are supplied by ibek; avoid reusing those
names. `env` is a Jinja global default, so an existing entity field or shared
variable called `env` takes precedence and remains compatible.

Unknown names in entity expressions raise an error containing the offending
template. Normal Jinja expressions, loops, tests and filters are available;
ibek adds no custom filters. Literal braces can be escaped with
`{% raw %}{{ literal }}{% endraw %}`.

(environment-variables)=
## Environment variables

The `env` mapping is new in the [unreleased changes](../release-notes.rst).
On older ibek releases, use `_global.get_env('NAME')`.

```jinja
{{ env.EPICS_ROOT }}
{{ env['EPICS_ROOT'] }}
{{ env.get('DEVICE_HOST', 'localhost') }}
```

`env` reads the environment of the running ibek process at render time, not
values that will be set later by generated `epicsEnvSet` commands. Values are
strings. A missing direct lookup fails in entity templates; `.get()` supplies
an explicit fallback. Use brackets for names that overlap mapping methods,
such as `env['items']` or `env['get']`. The mapping cannot be modified through
the template.

For a numeric parameter, convert explicitly:

```yaml
count:
  type: int
  description: Number of channels
  default: "{{ env.get('CHANNEL_COUNT', '4') | int }}"
```

`_global.get_env('NAME')` remains supported with unchanged behavior: it returns
an empty string when the variable is unset. There is no requirement to migrate
existing definitions.

## Typed expressions

Jinja produces text. ibek converts string expressions for typed `int`, `float`,
`bool`, `list` and `dict` parameters back into Python values. The result must
be a valid literal of the intended kind; `{{ count > 0 }}` produces a suitable
boolean. Native YAML values need no Jinja expression.

In untyped expansion contexts, such as repeat `values`, an expression ending
in `| list` or `| int` also tells ibek to recover the corresponding type:

```yaml
values: "{{ range(1, 5) | list }}"
```

Use only actual Jinja filters. In particular, `bool` and `dict` are not Jinja
filters: use a declared parameter type for those conversions, not `| bool` or
`| dict`.

## Shared helpers

These helpers share state across entities and render stages in a generation
run. Prefer parameters and object references for ordinary dependencies; use
shared state for values that need to accumulate across entities.

| Expression | Behavior |
| --- | --- |
| `_global.get_env(key)` | Environment string, or `''` if missing. |
| `_global.set(key, value)` | Store and return a shared value. |
| `_global.get(key, default='')` | Read a shared value, or return the default without storing it. |
| `_global.incrementor(name, start=0, increment=1, stop=None)` | First call returns `start`; later calls add `increment`. Errors if an existing value is not an integer or a later value exceeds `stop`. |

```yaml
pre_defines:
  address:
    description: Allocate a controller address
    type: int
    value: "{{ _global.incrementor('controller_address', start=1, stop=32) }}"
```

Stored values become bare names in subsequent renders; within the expression
that stores them, use the helper's return value or `_global.get`. Counters
advance per evaluation, so allocate once in a define and reuse the result
instead of incrementing separately in startup and database templates.

## Assembly templates

The packaged `st.cmd.jinja` joins the already rendered startup blocks. It sees
`env_var_elements`, `script_elements`, `post_ioc_init_elements`, `_global`,
shared helper variables and `env`. `ioc.subst.jinja` receives the grouped
`templates` data and `env`.

These assembly templates retain their existing permissive Jinja undefined
behavior; the strict missing-name errors described above apply to entity
expressions. Inserted startup blocks are already rendered text and are not
recursively evaluated by the assembly pass.
