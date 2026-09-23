# Where ibek fits

ibek is the configuration and build helper for
[epics-containers](https://epics-containers.github.io/main/). Its main runtime
job is to turn an IOC instance's YAML into an EPICS startup script and database
substitutions. It also provides tools for building generic IOC images and
preparing instance configuration outside containers.

## Images, definitions and instances

A **generic IOC image** contains an IOC executable, compiled EPICS support
modules, database templates and ibek. It can serve many devices without being
rebuilt for each one.

**Support YAML** describes the features that image exposes. Each file names a
module and declares **entity models**: typed parameters, startup commands and
database loads. These are commonly maintained in
[ibek-support](https://github.com/epics-containers/ibek-support), alongside the
recipes for building the corresponding EPICS modules.

An **IOC instance** supplies concrete entities in YAML. Its `type` values select
models such as `asyn.AsynIP`; other fields supply addresses, PV prefixes and
references to other entities. At boot, ibek validates these inputs against the
support definitions and renders the files for this instance.

## Responsibilities

| Component | Responsibility |
| --- | --- |
| EPICS support module | Driver code, record support and database templates |
| ibek-support | Module build recipes and support YAML exposing their features |
| Generic IOC project | Selects module versions and builds a reusable image |
| ibek | Schema generation, YAML validation, rendering and lifecycle helpers |
| Services repository | Instance YAML, runtime assets and deployment configuration |
| Docker Compose or Kubernetes | Runs and manages the container |

ibek does not require Kubernetes. The same rendering code runs on a workstation
with explicitly supplied definitions; running the resulting IOC requires EPICS
and the modules it references.

## Two ways to add support

Compiled drivers and libraries belong in the generic IOC image. Its support YAML
and published IOC schema describe those capabilities.

Runtime patterns add configuration files without rebuilding that image:
StreamDevice protocols, database templates, extra support YAML or entity YAML.
`ibek pattern` vendors these files into a services repository, records their
versions and builds a combined instance schema. A pattern cannot add a missing
compiled driver. Each instance carries its own copies, so the committed
instance alone answers what the IOC runs. See
[runtime pattern vendoring](../how-to/vendor-runtime-patterns.md),
[ADR 0003](decisions/0003-vendored-pattern-tag-is-authority.md) and
[ADR 0004](decisions/0004-vendor-runtime-support-over-submodules.md).

Start with [a local render](../tutorials/build-an-ioc.md) to learn ibek itself.
For complete workflows, use the epics-containers guides to
[build a generic IOC](https://epics-containers.github.io/main/tutorials/generic_ioc.html),
[create an instance](https://epics-containers.github.io/main/tutorials/create_ioc.html)
and [run it with Compose](https://epics-containers.github.io/main/how-to/compose-quickstart.html).
