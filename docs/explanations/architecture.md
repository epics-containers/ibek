# Architecture and data flow

This page explains how `ibek` turns hand-authored support YAML into a running
IOC instance: which files exist, which command produces each one, and how the
internal modules fit together. It is aimed at contributors and advanced users.
For concept-level orientation start with the [overview](overview.md); for the
exact commands, options and field tables see the
[CLI reference](../reference/cli.md),
[support YAML reference](../reference/support-yaml.md) and
[ioc YAML reference](../reference/ioc-yaml.md).

## The file and schema lifecycle

`ibek` is split across three lifecycle phases — building a support image,
building a generic IOC image, and booting an IOC instance — each of which
produces and consumes specific files. The diagram below replaces the older
hand-drawn architecture image and uses the current file names throughout.

```{mermaid}
flowchart TD
    subgraph author["Support module authoring (under ibek-support)"]
        sup["*.ibek.support.yaml<br/>(one per support module)"]
    end

    subgraph supbuild["Support image build"]
        gss["ibek support generate-schema"]
        supschema["ibek.support.schema.json<br/>(global schema: validates<br/>every *.ibek.support.yaml)"]
        gss --> supschema
        supschema -. "editor validation" .-> sup
    end

    subgraph iocbuild["Generic-IOC image build"]
        gis["ibek ioc generate-schema<br/>(combines ALL support yaml)"]
        entschema["&lt;container&gt;.ibek.ioc.schema.json<br/>(generic-IOC entities schema;<br/>published to the release under<br/>the fixed name ibek.ioc.schema.json)"]
        gis --> entschema
    end

    subgraph instance["IOC instance authoring + boot"]
        iocyaml["*.ibek.ioc.yaml<br/>(instance author writes this)"]
        gen["ibek runtime generate / generate2<br/>(at container boot)"]
        stcmd["st.cmd<br/>(EPICS startup script)"]
        subst["ioc.subst<br/>(+ generated .db / pvi)"]
        iocyaml --> gen
        gen --> stcmd
        gen --> subst
    end

    sup --> gss
    sup --> gis
    entschema -. "editor validation" .-> iocyaml
    entschema --> gen
```

Reading the diagram:

- A support-module author writes one `*.ibek.support.yaml` per module. Each one
  is validated against the single global `ibek.support.schema.json`, produced by
  [`ibek support generate-schema`](../reference/cli.md). That schema is derived
  from the `Support` pydantic model, so it describes the *shape of a support
  file*, not the entities a particular image offers.
- At generic-IOC build time, [`ibek ioc generate-schema`](../reference/cli.md)
  reads all the support YAML baked into the image and emits the **entities
  schema** — generated locally as `<container>.ibek.ioc.schema.json`. This schema
  enumerates the concrete entity types the image can instantiate, and is
  published as a GitHub release artifact alongside the container image under the
  fixed name `ibek.ioc.schema.json` (no container prefix).
- An instance author writes `*.ibek.ioc.yaml`, validated in their editor against
  that entities schema.
- At container boot, [`ibek runtime generate`](../reference/cli.md) (or the
  newer `generate2`, which accepts multiple instance files) renders the EPICS
  startup script `st.cmd` **and** the database substitution file `ioc.subst`
  (plus generated `.db` and PVI/OPI files). Both outputs are first-class
  products of the same render pass.

```{note}
The retired names `ibek.defs.schema.json` and
`<container>.ibek.entities.schema.json` no longer appear anywhere in the code
or the produced artifacts. If you see them in older material, read them as
`ibek.support.schema.json` and `<container>.ibek.ioc.schema.json`
respectively.
```

## The internal module pipeline

Inside a single `ibek runtime generate` invocation the work flows through four
collaborating modules. The function `do_generate` in
`runtime_cmds/commands.py` is the orchestrator that wires them together.

```{mermaid}
flowchart LR
    yaml["*.ibek.support.yaml"] --> ef
    ioc["*.ibek.ioc.yaml"] --> if

    subgraph ef_box["EntityFactory"]
        ef["make_entity_models()<br/>one dynamic Entity class<br/>per EntityModel"]
    end

    subgraph if_box["IocFactory"]
        if["make_ioc_model() unions the<br/>Entity classes into the IOC model<br/>(discriminated by 'type')"]
        des["deserialize_ioc()<br/>builds Entity instances"]
        if --> des
    end

    ef --> if

    subgraph render_box["gen_scripts + Render / RenderDb"]
        r["create_boot_script (Render)"]
        rdb["create_db_script (RenderDb)"]
    end

    des --> r --> stcmd["st.cmd"]
    des --> rdb --> subst["ioc.subst"]
```

What each stage does:

- **`EntityFactory` builds the types.** `make_entity_models()` reads each
  `*.ibek.support.yaml`, validates it with the `Support` model, then calls
  `create_model()` to mint one *dynamic pydantic `Entity` subclass* per
  `EntityModel`. The equivalence "one `EntityModel` instance == one `Entity`
  class" is central: instantiating an `EntityModel` *is* creating a new entity
  type. The builtin `ibek.*` types (`RepeatEntity`, `Wait4IPEntity`,
  `Wait4USBEntity`) are added to the same registry.
- **`IocFactory` unions them and deserialises.** `make_ioc_model()` takes the
  list of Entity classes and forms a discriminated `Union` (keyed on the `type`
  literal of each class) to produce an `IOC` model whose `entities` field
  accepts any of them. This same model, serialised with
  `model_json_schema()`, is exactly the entities schema published at build
  time. `deserialize_ioc()` then loads an `*.ibek.ioc.yaml` and validates it
  against that model, yielding concrete `Entity` *instances*.
- **`Render` and `RenderDb` emit the outputs.** Back in `do_generate`,
  `create_boot_script()` (using `Render`) walks the entity instances and emits
  `st.cmd`, while `create_db_script()` (using `RenderDb`) emits `ioc.subst`.

A few cross-cutting details that explain *why* the modules look the way they
do:

- **Pydantic models define the schema.** The `Param` subclasses
  (`ObjectParam`, `IdParam`, `EnumParam`, and the scalar params) plus
  `EntityModel` are ordinary pydantic models. The JSON schemas at every phase
  are just `model_json_schema()` output, so the schema can never drift from the
  validation logic.
- **Rendering order is fixed by a model validator.** The `add_ibek_attributes`
  `model_validator(mode="after")` in `ioc.py` performs Jinja rendering of an
  entity's fields in the order `pre_defines` -> `parameters` -> `post_defines`,
  and stashes the defines on the instance so they are available to the final
  render pass.
- **`UTILS` performs two-phase Jinja.** `utils.py` holds the singleton `UTILS`
  renderer. Phase one runs during deserialisation (the model validator above);
  phase two runs while `Render`/`RenderDb` build the output files, with a shared
  global context (`_global`, `ioc_name`, variables created via `set`/`get`).
  The template context available to authors is documented in the
  [Jinja context reference](../reference/jinja-context.md).

## CLI groups mapped to lifecycle phases

`ibek`'s top-level command groups (see `__main__.py`) line up with the
lifecycle phases above:

| CLI group | Lifecycle phase | Role |
|-----------|-----------------|------|
| `ibek support` | Support image build | Compile/install support modules and emit the global `ibek.support.schema.json`. |
| `ibek ioc`     | Generic-IOC image build | Combine all support YAML into the published entities schema; `ibek ioc do-wait` also runs at instance **runtime** to block boot until hardware is reachable. |
| `ibek runtime` | IOC instance boot | Render `st.cmd`, `ioc.subst` and runtime assets from the instance YAML. |
| `ibek dev`     | Developer containers | Helpers for working *inside* a generic-IOC development container. |
| `ibek pattern` | Services repository | Vendor runtime-support patterns into a services repo and build the instance schema (see below). |

The **Role** column paraphrases each group's purpose for this page; it is not
the literal Typer `--help` text. The full command and option listing is in the
[CLI reference](../reference/cli.md); it is generated directly from the Typer
app so it cannot drift from the code.

## The runtime-support vendoring layer

The two diagrams above describe the build-time flow that predates the
`ibek pattern` feature. Vendoring adds a per-instance layer on top, so a
services repository can pin and carry the runtime support it needs without
rebuilding the generic-IOC image.

- Each IOC instance keeps **vendored copies** of the support patterns it uses,
  pinned by a lock file named `runtime-lock.yaml` (`RUNTIME_LOCK_NAME` in
  `globals.py`). The lock records exactly which version of each pattern the
  instance is using.
- [`ibek pattern schema`](../reference/cli.md) builds a **self-contained**
  instance schema. It fetches the image's *published base entities schema*
  (the release asset `ibek.ioc.schema.json`) and programmatically merges the
  instance's vendored and local support entities into the base schema's
  discriminated `oneOf` / `discriminator.mapping` / `$defs`. The result is
  written as `ioc.schema.json` (`IOC_SCHEMA_NAME`) at the instance root, and
  the `ioc.yaml` schema header is rewritten to point at it.
- At boot, `ibek runtime generate2` picks up both the image's own support
  definitions and the vendored support found in the instance config folder, so
  the instance can add entities that the base image never knew about.

This supersedes an earlier design that wired support into the services repo
using git submodules and symlinks. The move from submodules to vendored copies,
and the reasons for it, are recorded in
[ADR 0004](decisions/0004-vendor-runtime-support-over-submodules.md); the
related decision that the vendored pattern tag is the source of authority is
[ADR 0003](decisions/0003-vendored-pattern-tag-is-authority.md).

This page stays at the architecture level — the operational steps for
vendoring, checking and restoring patterns live in the
[vendoring how-to](../how-to/vendor-runtime-patterns.md).

## See also

- [Overview](overview.md) — concepts and terminology.
- [CLI reference](../reference/cli.md) — every command and option.
- [Support YAML reference](../reference/support-yaml.md) — fields of
  `*.ibek.support.yaml` and the schema artifacts.
- [ioc YAML reference](../reference/ioc-yaml.md) — fields of
  `*.ibek.ioc.yaml`.
- [Jinja context reference](../reference/jinja-context.md) — what templates can
  reference.
- [Architecture decision records](decisions.md) — the ADR index.
