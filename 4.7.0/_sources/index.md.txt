---
html_theme.sidebar_secondary.remove: true
---

# ibek

ibek turns IOC instance YAML and reusable support definitions into an EPICS
startup script and database substitutions. It also helps prepare generic IOC
images and manage runtime patterns in services repositories.

Start with [installation](tutorials/installation.md) and
[render a small IOC configuration](tutorials/build-an-ioc.md).
For a specific task, use the [CLI reference](reference/cli.md),
[Jinja context](reference/jinja-context.md), or
[support-definition reference](reference/support-yaml.md).

These pages document ibek itself. The
[epics-containers documentation](https://epics-containers.github.io/)
covers the wider workflow: creating generic IOC images, configuring services,
and deploying IOCs. [How ibek fits](explanations/overview.md) connects the two.

::::{grid} 2
:gutter: 3

:::{grid-item-card} Tutorials
Install ibek and generate your first startup files.

```{toctree}
:maxdepth: 1

tutorials
```
:::

:::{grid-item-card} How-to guides
Write support definitions, vendor runtime patterns, and diagnose problems.

```{toctree}
:maxdepth: 1

how-to
```
:::

:::{grid-item-card} Reference
Commands, YAML fields, template context, paths and environment variables.

```{toctree}
:maxdepth: 1

reference
```
:::

:::{grid-item-card} Explanations
The framework, ibek-support, and the path from YAML to a running IOC.

```{toctree}
:maxdepth: 1

explanations
```
:::

::::
