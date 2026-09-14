# Build your first IOC instance

This tutorial walks you end to end through turning a support module
definition into a running EPICS IOC startup script, using the `motorSim`
simulated‑motion sample that ships with `ibek`. By the end you will have:

1. read a *support definition* file and understood what it declares,
2. generated a JSON *schema* for authoring instances,
3. written an *IOC instance* file,
4. generated the *runtime* files an IOC needs to boot, and
5. compared the produced `st.cmd` against the known‑good sample.

Every command here is real and tested. Inside a generic IOC container the
`ibek` command is already on the `PATH`, so type the commands exactly as
shown. If you are following along in a checkout of this repository instead,
prefix each command with `uv run` (the first run rebuilds the virtual
environment, so give it a moment).

The bare file names below assume the container layout, where the support and
instance files sit in the working directory. In a checkout they live under
`tests/samples/support/`, `tests/samples/iocs/` and `tests/samples/outputs/`,
so either `cd tests/samples` first and prefix the names with `support/`,
`iocs/` and `outputs/`, or pass the full paths.

## The three phases

`ibek` is used at three different points in an IOC's life. Keep this map in
mind as you go — each step below belongs to one of these phases.

```{mermaid}
flowchart LR
    A[Container build phase<br/>support modules + their<br/>.ibek.support.yaml defs<br/>baked into the image] --> B[Authoring phase<br/>generate schema,<br/>write the instance YAML]
    B --> C[Boot phase<br/>runtime generate -><br/>st.cmd + runtime db,<br/>then the IOC starts]
```

Steps 1–3 are **authoring**: a developer does them once to create an IOC
instance. Step 4 belongs to the **boot phase**: when an IOC container starts
it regenerates these files. Production containers do this with the newer
`generate2` subcommand; this tutorial uses the simpler legacy single‑instance
`generate`, which is enough for one instance file. The support modules
referenced in step 1 were compiled and their definition files collected during
the earlier **container build phase**.

## Step 1 — start from a support definition file

A support module ships an `*.ibek.support.yaml` file that declares one or
more **Entity Models** — the building blocks you can later instantiate in an
IOC. Open the sample:

`tests/samples/support/motorSim.ibek.support.yaml`

```{literalinclude} ../../tests/samples/support/motorSim.ibek.support.yaml
:language: yaml
:lines: 6-57
```

The top‑level `module` names the support module, and `entity_models` is the
list of models it provides. The first model above, `simMotorController`,
declares its `parameters` (typed inputs such as `controllerName`, `P`,
`numAxes` and a `port` of `type: object`), the `pre_init` startup‑script
snippet it contributes, and the `databases` and `pvi` it brings. A second
model, `simMotorAxis`, follows further down the file.

For the full meaning of every field, see the
[support YAML reference](../reference/support-yaml.md).

## Step 2 — generate the entities schema

To author an instance with editor autocompletion and validation, turn the
support definitions into a JSON schema:

```bash
ibek ioc generate-schema \
    motorSim.ibek.support.yaml asyn.ibek.support.yaml \
    --no-ibek-defs \
    --output motorSim.ibek.ioc.schema.json
```

The `--no-ibek-defs` flag tells `ibek` to build the schema **only** from the
files you list, instead of also pulling in the support definitions bundled
into a generic IOC container. That is exactly what you want when you are
working outside a container (as in this tutorial) — you supply the
definitions yourself.

We pass both `motorSim` *and* `asyn` because the instance we are about to
write uses an entity from each module; the generated schema must know about
every model the instance references.

## Step 3 — author the IOC instance

An IOC instance file lists the concrete entities you want, each one an
instance of a model from step 1. Here is the sample:

`tests/samples/iocs/motorSim.ibek.ioc.yaml`

```{literalinclude} ../../tests/samples/iocs/motorSim.ibek.ioc.yaml
:language: yaml
```

Three things to notice:

- **`ioc_name`** identifies the IOC. Here it uses the Jinja value
  `{{ ioc_yaml_file_name }}`, which `ibek` fills in from the instance
  file's own name.
- **`type:`** on each entity selects a model using `module.model`
  notation — `asyn.AsynIP`, `motorSim.simMotorController`,
  `motorSim.simMotorAxis`.
- **Object references** wire entities together. The `simMotorController`'s
  `port` is set to `controllerOnePort` (the `name` of the `asyn.AsynIP`
  entity above it), and each `simMotorAxis` sets `controller` to
  `controllerOne` (the controller's `controllerName`). `ibek` validates
  these references, so a typo is caught early.

The first line is a `yaml-language-server` comment pointing at the schema
from step 2 — that is what gives you autocompletion in a YAML‑aware editor.

For the field‑by‑field details see the
[IOC YAML reference](../reference/ioc-yaml.md), and for how the `{{ ... }}`
templating is evaluated see the
[Jinja context reference](../reference/jinja-context.md).

## Step 4 — generate the runtime files

Now produce the files the IOC needs to boot. The `generate` subcommand used
here is the legacy single‑instance form (production containers run `generate2`
at startup); it is the simplest way to follow along with one instance file:

```bash
ibek runtime generate \
    motorSim.ibek.ioc.yaml \
    motorSim.ibek.support.yaml asyn.ibek.support.yaml \
    --no-pvi \
    -o /tmp/runtime
```

The first argument is the instance file; the remaining arguments are the
support definition files for **every** module the instance uses — again both
`motorSim` and `asyn`. The `-o` option chooses the output folder. The
`--no-pvi` flag skips generating PVI screens, which `ibek` would otherwise
write to `/epics/opi` regardless of `-o` — a path that only exists inside a
container, so the command fails without it when run from a checkout.

```{note}
Inside a real IOC container these support definition files live in a known
location that was populated during the container build phase, and the
EPICS environment variables that set the IOC and runtime paths are already
exported. In this tutorial's sandbox those variables are unset, so the
absolute paths in the generated script differ slightly — the structure is
identical.
```

## Step 5 — inspect the generated `st.cmd`

Look at `/tmp/runtime/st.cmd`. It should match the tested sample at
`tests/samples/outputs/motorSim/st.cmd`:

```{literalinclude} ../../tests/samples/outputs/motorSim/st.cmd
:language: shell
```

Trace it back to your inputs:

- The `AsynIPConfigure(...)` line came from the `asyn.AsynIP` entity.
- `motorSimCreateController(controllerOne, 4)` is the `simMotorController`'s
  `pre_init` snippet, with `{{controllerName}}` and `{{numAxes}}` filled in.
- The block of `motorSimConfigAxis(...)` lines are the `post_init` snippets
  of each `simMotorAxis`, in the order you declared them.

Alongside `st.cmd` you will also find `ioc.subst`, the substitution file that
expands into the runtime EPICS database. Together these are everything the
IOC binary needs to start.

## Where to go next

- The [CLI reference](../reference/cli.md) documents every command and option
  used above (`ibek ioc generate-schema`, `ibek runtime generate`, and more).
- The [support YAML](../reference/support-yaml.md) and
  [IOC YAML](../reference/ioc-yaml.md) references describe the two file
  formats in full.
- The [Jinja context reference](../reference/jinja-context.md) lists the
  variables and helpers available inside `{{ ... }}` templates.
- For the bigger picture of how these pieces fit together, read
  [the overview](../explanations/overview.md).
