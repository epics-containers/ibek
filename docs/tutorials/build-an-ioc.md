# Render an IOC configuration

This example runs outside a container with only [ibek installed](installation.md).
It generates startup and substitution files; running the IOC would additionally
require EPICS and the referenced database template.

## Define one entity model

Work in a new directory:

```bash
mkdir ibek-example
cd ibek-example
cat > demo.ibek.support.yaml <<'YAML'
module: demo
entity_models:
  - name: Status
    description: A status record with an IOC startup message
    parameters:
      P:
        type: str
        description: PV prefix
    pre_init:
      - type: comment
        value: "Configure {{ P }}status"
    databases:
      - file: status.template
        args:
          P:
YAML
```

The empty database argument value means “use the parameter with this name”.
`status.template` is an EPICS database template filename; ibek records its use
without needing to open the file.

## Generate a schema and write an instance

```bash
ibek ioc generate-schema demo.ibek.support.yaml \
    --no-ibek-defs --output ioc.schema.json
mkdir config
cat > config/ioc.yaml <<'YAML'
# yaml-language-server: $schema=../ioc.schema.json
ioc_name: demo
description: A minimal rendering example
entities:
  - type: demo.Status
    P: "DEMO:"
YAML
```

`--no-ibek-defs` makes schema generation use only the supplied support file.
The schema comment enables completion and checking in a YAML-aware editor.

## Render and inspect

```bash
IOC=/epics/ioc RUNTIME_DIR=/epics/runtime \
    ibek runtime generate2 config \
    --definitions demo.ibek.support.yaml --no-pvi --output generated
cat generated/st.cmd
cat generated/ioc.subst
```

Use a dedicated output directory: rendering replaces its contents. `--no-pvi`
skips UI generation and its container-specific output paths. `IOC` and
`RUNTIME_DIR` here provide paths written into the script; they do not need to
exist for this render.

`st.cmd` contains `# Configure DEMO:status`, followed by the standard database
load and IOC initialization. `ioc.subst` contains a `status.template` block with
macro `P` set to `DEMO:`. Changing `P` and rendering again changes both outputs.
The instance is also validated during rendering: try removing `P` to see the
missing-parameter error.

Next, [connect a controller and its motors](connect-entities.md) to see how
entities refer to each other using real support definitions.
To expose a real module, see [writing support](../how-to/write-support.md).
For the remaining steps to build and run a container, follow the
[epics-containers generic IOC tutorial](https://epics-containers.github.io/main/tutorials/generic_ioc.html).
