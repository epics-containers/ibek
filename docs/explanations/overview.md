# Overview: what ibek is and its core concepts

ibek (IOC Builder for EPICS and Kubernetes) is the
[epics-containers](https://epics-containers.github.io/main/) tool for building
EPICS IOCs that run in containers and Kubernetes. It lets you *declaratively*
describe an EPICS IOC instance in YAML — which devices it talks to and how they
are configured — and then renders the EPICS startup script (`st.cmd`) and
database that boot that IOC. Instead of hand-writing and maintaining boot
scripts and substitution files per IOC, you write a short, schema-validated YAML
file and let ibek generate the rest at container runtime.

This page introduces the ideas and vocabulary you need before reading anything
else. It deliberately stays at the conceptual level: it does not document
individual commands, YAML fields, or module internals — those live in the
{doc}`reference <../reference>` pages and in
{doc}`architecture <architecture>`.

## Who ibek is for

ibek serves two distinct audiences, and most of the documentation is organised
around the boundary between them.

- **Generic IOC / container developers** build the container images. They pick a
  set of EPICS support modules, write the YAML that exposes each module's
  features, and produce a reusable image (for example `ioc-pmac`). They care
  about how support is described and how an image's schema is published.
- **IOC instance designers and operators** consume those images. They write a
  small YAML file that says "run *this* generic IOC, talking to *these* devices,
  with *these* addresses and macros", validate it against the image's published
  schema, and deploy it to Kubernetes. They rarely touch C code or build images.

The clean split between these roles is the central design idea: a developer
publishes *capability* (an image plus a schema describing what it can do), and an
operator declares *intent* (one instance's configuration) against that schema.

## Generic IOCs versus IOC instances

The most important distinction in epics-containers is between a **generic IOC**
and an **IOC instance**:

- A **generic IOC** is a *container image* that bundles a chosen set of EPICS
  support modules together with their libraries, DB templates and `ibek`
  itself. It is generic because, on its own, it is not configured to talk to any
  particular hardware — it is the reusable "kit of parts". `ioc-pmac`, which
  bundles the `pmac` and `motor` support modules, is a typical example.
- An **IOC instance** is a *YAML description* of what one running IOC should do
  with a generic IOC image: which entities to create, which devices to connect
  to, and what addresses and macros to use. The image supplies the capability;
  the instance supplies the specifics.

The same generic IOC image is reused by many instances — a single `ioc-pmac`
image can back dozens of motion IOCs that differ only in their instance YAML.
For a fuller treatment of this distinction across the whole epics-containers
ecosystem, see the upstream explanation
[Generic IOCs and instances](https://epics-containers.github.io/main/explanations/introduction.html#generic-iocs-and-instances).

## Entity Models and Entities

A generic IOC needs a machine-readable description of *what features its support
modules offer*. ibek expresses this with **Entity Models**.

An **Entity Model** (implemented by the `EntityModel` class) describes one class
of thing an IOC instance can create — a controller, a port, an axis, a detector
plugin, and so on. Each Entity Model declares:

- the parameters an instance must (or may) supply,
- the startup-script snippets to emit, as Jinja templates that reference those
  parameters,
- the EPICS databases to load, with macros taken from those parameters.

```{note}
Entity Models were previously called **Definitions** in older ibek
documentation and YAML. The current term is *Entity Model*; if you encounter
"Definition" in historical material, read it as "Entity Model".
```

Each support module ships its Entity Models in a file named
`<module>.ibek.support.yaml`, which lives alongside the module inside the
generic IOC image. A generic IOC therefore contains a collection of these
support YAML files — one per support module it bundles.

An **Entity** is a single instance of an Entity Model, created by an IOC
instance. In the instance's YAML each entity carries a `type` of the form
`<module>.<EntityModelName>` (for example `motorSim.simMotorController`), which names exactly
which Entity Model, from which module, it instantiates. ibek looks up that
model, validates the supplied parameters against it, and renders the
corresponding startup-script lines and database loads. The set of entities in an
instance, taken together, is the IOC: declaring entities is how an instance
author expresses everything the IOC should do.

So the two halves fit together like a type and its values: support modules
declare Entity Models (the available types), and an IOC instance declares
Entities (typed values) that ibek turns into a working `st.cmd` and EPICS
database.

## The build-and-run lifecycle

ibek's work is split across two phases — container *build* time and container
*runtime* — with a published schema acting as the contract between them.

1. **Author support YAML.** A generic IOC developer writes (or inherits from the
   support modules) one `*.ibek.support.yaml` file per module, each declaring
   that module's Entity Models.
2. **Combine into a schema at build time.** When the generic IOC image is built,
   ibek merges all of the bundled support YAML files into a single *entities
   schema* — a JSON Schema describing every entity type the image can run. This
   schema is published as a GitHub artifact released alongside the image, so an
   instance author can obtain it without pulling the whole image.
3. **Write the instance YAML.** An IOC instance designer writes an
   `*.ibek.ioc.yaml` file listing the entities the IOC needs. Their editor
   validates this file against the image's published entities schema, catching
   wrong types, missing parameters and typos before anything is deployed.
4. **Render at runtime.** When the instance's container starts, ibek reads the
   instance YAML and the support YAML present in the image and renders the EPICS
   startup script (`st.cmd`) and the substitution/database files the IOC needs to
   boot.

The important property is that the schema an operator validates against is
generated from the very support files the image will use at runtime, so the
thing they design against and the thing that runs cannot silently diverge. The
detailed data flow and the file/command sequence are covered in
{doc}`architecture <architecture>`.

## Runtime-support pattern vendoring

Some runtime inputs an IOC needs are not compiled into the image and are not
naturally expressed as inline entity parameters: StreamDevice `.proto` and
`.protocol` files, AreaDetector plugin sets, extra `*.ibek.support.yaml`, and
their associated `db`/template files. ibek manages these with a **pattern
vendoring** mechanism, driven by the `ibek pattern` commands.

A *pattern* is a named, versioned file-set held in a central library — for
example `ibek-runtime-streamdevice` or `ibek-runtime-support`. Rather than
sharing those files by reference, each IOC instance **vendors its own copy**:
`ibek pattern` copies the file-set into the instance's `config/`, stamps each
file with a `# Vendored from <source>@<version> — DO NOT EDIT` header, and
records every file's SHA-256 in a `runtime-lock.yaml` at the instance root. The
committed instance is then self-contained — the lock answers "what is this IOC
actually running?" without depending on anything outside the instance.

This **replaces an older git-submodule-plus-symlink model**, in which a
pattern's effective version was tied to the build image and to whatever the
symlinks resolved to, rather than to the committed instance.

Two points about the lock are worth fixing in your mind, because they shape how
`update`, `restore` and `check` behave:

- **The upstream tag is the source of truth.** Patterns are pinned by an
  immutable upstream tag; re-vendoring that tag always produces the same bytes.
  To change what an instance runs, you move the pin to a new tag.
- **The lock's SHA-256 entries are a local-drift integrity check only.** They
  exist so `ibek pattern check` can detect hand-edits to vendored files. They are
  *not* a content store and *not* a tamper-evident pin against upstream.

To actually vendor, update, check and restore patterns, follow the how-to guide
{doc}`Vendor runtime-support patterns <../how-to/vendor-runtime-patterns>`. The
reasoning behind this design is recorded in the architecture decision records
{doc}`ADR 3 — Vendored pattern tag is the authority <decisions/0003-vendored-pattern-tag-is-authority>`
and
{doc}`ADR 4 — Vendor runtime support over submodule + symlink <decisions/0004-vendor-runtime-support-over-submodules>`.

## Where to go next

- {doc}`Build an IOC <../tutorials/build-an-ioc>` — a hands-on, end-to-end
  tutorial that turns a sample instance YAML into a working `st.cmd`.
- {doc}`Architecture <architecture>` — the module structure, the full data flow,
  and the file/command sequence behind the lifecycle described above.
- {doc}`Reference <../reference>` — the CLI, the support and IOC YAML schemas
  field by field, and the Jinja rendering context.
