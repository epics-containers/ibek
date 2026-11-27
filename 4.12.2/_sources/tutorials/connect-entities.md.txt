# Connect a controller and its motors

The [first tutorial](build-an-ioc.md) rendered one independent entity. This
example connects four: an IP connection, a GeoBrick controller and two motor
records. It uses real definitions from ibek-support to show how `id` and
`object` parameters connect startup commands and database macros.

You need ibek and Git. Rendering needs neither EPICS nor a connection to hardware;
starting the generated IOC would require an appropriate generic IOC image.

## Get the support definitions

Use a separate directory and a fixed ibek-support release for this example:

```bash
mkdir ibek-motion-example
cd ibek-motion-example
git clone --depth 1 --branch 3.4.2 \
    https://github.com/epics-containers/ibek-support.git
mkdir config
ibek ioc generate-schema ibek-support/pmac/pmac.ibek.support.yaml \
    --no-ibek-defs --output ioc.schema.json
```

This reads the module's support YAML; it does not build or install PMAC.

## Declare the connected entities

Save this as `config/ioc.yaml`:

```yaml
# yaml-language-server: $schema=../ioc.schema.json
ioc_name: motion
description: One controller with two motor records
entities:
  - type: pmac.pmacAsynIPPort
    name: BRICK1port
    IP: "192.0.2.10:1025"

  - type: pmac.GeoBrick
    name: BRICK1
    pmacAsynPort: BRICK1port
    P: "DEMO:CTRL:"
    NAXES: 2

  - type: pmac.dls_pmac_asyn_motor
    Controller: BRICK1
    P: "DEMO:"
    M: X
    ADDR: 1
    DESC: Horizontal axis
    MRES: 0.001
    EGU: mm
    DLLM: -10
    DHLM: 10

  - type: pmac.dls_pmac_asyn_motor
    Controller: BRICK1
    P: "DEMO:"
    M: Y
    ADDR: 2
    DESC: Vertical axis
    MRES: 0.001
    EGU: mm
    DLLM: -10
    DHLM: 10
```

The connection and controller declare their `name` parameters as `type: id`.
The controller's `pmacAsynPort` and each motor's `Controller` are `type: object`:
ibek resolves their strings to previously declared entities. Order therefore
matters: connection first, then controller, then motors. These references use
IDs, not entity type names or PV prefixes.

## Render and trace the outputs

```bash
IOC=/epics/ioc RUNTIME_DIR=/epics/runtime \
    ibek runtime generate2 config \
    --definitions ibek-support/pmac/pmac.ibek.support.yaml \
    --no-pvi --output generated
cat generated/st.cmd
cat generated/ioc.subst
```

As in the first tutorial, use a dedicated output directory: generation replaces
its contents. The paths assigned to `IOC` and `RUNTIME_DIR` are written into the
startup script and need not exist for this render.

Among the generated startup lines are:

```text
pmacAsynIPConfigure("BRICK1port", "192.0.2.10:1025")
pmacCreateController("BRICK1", "BRICK1port", 0, 2, 100, 500)
pmacCreateAxes("BRICK1", 2)
```

The connection contributes the first command. The controller contributes the
next two, using `{{ pmacAsynPort }}` to render the referenced connection's ID.
The motor entities contribute two rows for `dls_pmac_asyn_motor.template` in
`ioc.subst`. Selected macros show how their object references are used:

| Macro | Expression in the support definition | X motor | Y motor |
| --- | --- | --- | --- |
| `PORT` | `{{ Controller }}` | `BRICK1` | `BRICK1` |
| `PMAC` | `{{ Controller.P }}` for these physical axes | `DEMO:CTRL:` | `DEMO:CTRL:` |
| `P` | Own parameter | `DEMO:` | `DEMO:` |
| `M` | Own parameter | `X` | `Y` |
| `ADDR` | Own parameter | `1` | `2` |

An entity can thus contribute startup commands, database instances, or both.
`{{ Controller }}` yields an ID; `{{ Controller.P }}` accesses a field on the
same object. Neither requires copying the controller's settings into each motor.

The connection definition also creates a hardware-wait sub-entity, producing
`wait_list.yaml`. Generation writes the list without waiting or connecting to
this example address. At real IOC startup, separate tooling processes that list
and expands `ioc.subst` with EPICS `msi`.

Try changing only the controller's `P` to `"DEMO:OTHER:"` and rendering again:
both motor rows inherit the new `PMAC` value while their own `P` remains
`DEMO:`. Changing a motor's `Controller` to an unknown ID instead produces a
validation error. This is the benefit of declaring relationships explicitly.

For the lookup and rendering rules, see [Jinja context](../reference/jinja-context.md).
To expose another module's features, continue with
[writing support](../how-to/write-support.md).
