# Install ibek

Generic IOC containers already include ibek. Install it on your workstation to
manage runtime patterns, generate schemas or render configuration without
starting an IOC. Python 3.13 or newer is required.

For an isolated command-line installation with `uv`:

```bash
uv tool install ibek
ibek --version
ibek --help
```

Alternatively, use a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ibek
ibek --version
```

The Python package does not install EPICS, support modules or a generic IOC.
Build and development helpers expect the environment supplied by an
[epics-containers developer container](https://epics-containers.github.io/main/tutorials/dev_container.html).

Continue with [Render an IOC configuration](build-an-ioc.md), which needs only
ibek. For work on ibek's own source, see [contributing](../how-to/contribute.md).
