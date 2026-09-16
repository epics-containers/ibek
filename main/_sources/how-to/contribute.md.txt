# Develop ibek

Work on the Python CLI and renderer in this repository. EPICS module recipes
and their entity definitions normally belong in
[ibek-support](https://github.com/epics-containers/ibek-support).

From a checkout, with Python 3.13 or newer and `uv` available:

```bash
uv sync
uv run ibek --help
uv run tox -p
```

`tox -p` runs formatting and lint checks, type checking, tests and the Sphinx
build. For a focused change:

```bash
uv run pytest tests/test_runtime.py
uv run tox -e docs
```

Tests under `tests/` include sample support YAML, instance YAML and expected
rendered files in `tests/samples/`. When changing rendering behavior, check the
resulting startup script and substitution file, and add a regression test for
the behavior being changed. The Python suite does not replace running a real
IOC when changing EPICS integration.

The implementation path is described in
[files and lifecycle](../explanations/architecture.md). Report bugs and propose
changes through [GitHub issues](https://github.com/epics-containers/ibek/issues);
include the ibek version, command, relevant YAML and expected output.
