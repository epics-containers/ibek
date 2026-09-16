[![CI](https://github.com/epics-containers/ibek/actions/workflows/ci.yml/badge.svg)](https://github.com/epics-containers/ibek/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/epics-containers/ibek/branch/main/graph/badge.svg)](https://codecov.io/gh/epics-containers/ibek)
[![PyPI](https://img.shields.io/pypi/v/ibek.svg)](https://pypi.org/project/ibek)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

# ibek

ibek is the IOC builder for [epics-containers](https://epics-containers.github.io/).
It combines reusable support definitions with an IOC instance's YAML to generate
its startup script and database substitutions. A generic IOC image supplies the
compiled EPICS support; instance configuration selects what that image runs.

The CLI supports several stages of that workflow:

| Where | Commands | Purpose |
| --- | --- | --- |
| Container build | `ibek support`, `ibek ioc` | Prepare support, schemas and generic IOC assets. |
| Running IOC container | `ibek runtime` | Generate startup files, databases and related runtime assets. |
| Development container | `ibek dev` | Connect an IOC instance checkout to the development environment. |
| Services checkout, outside the IOC container | `ibek pattern` | Vendor runtime patterns and compose the instance schema. |

See the [CLI reference](https://epics-containers.github.io/ibek/main/reference/cli.html)
for individual commands and exceptions to these groupings.

Install the standalone CLI with Python 3.13 or later:

```bash
uv tool install ibek
ibek --help
```

EPICS build and runtime operations also need the tools and directory layout
provided by the appropriate IOC container.

[Read the documentation](https://epics-containers.github.io/ibek/) for a small
rendering tutorial, YAML and Jinja references, and how ibek uses ibek-support.
For creating and deploying complete IOCs, use the
[epics-containers documentation](https://epics-containers.github.io/).

[Source](https://github.com/epics-containers/ibek) ·
[Releases](https://github.com/epics-containers/ibek/releases)
