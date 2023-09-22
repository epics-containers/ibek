ibek: IOC Builder for EPICS and Kubernetes
==========================================

|code_ci| |docs_ci| |coverage| |pypi_version| |black| |license|


This tool supports building container images for Generic EPICS IOCs and
generating IOC Instances from those Generic IOCs at container runtime. It is
targetted at running IOCs in Kubernetes, but the images it
creates can execute in any container runtime, such as docker or podman.

  ============== ==============================================================
  PyPI           ``pip install ibek``
  Source code    https://github.com/epics-containers/ibek
  Documentation  https://epics-containers.github.io/ibek
  Releases       https://github.com/epics-containers/ibek/releases
  ============== ==============================================================


The documentation is still under construction. For the moment the best
pages to read are the following:

- `Modules, Definitions and Entities <https://epics-containers.github.io/ibek/main/developer/explanations/entities.html//>`_
  A description of the basic concepts of ibek.

- `naming conventions in support YAML <https://epics-containers.github.io/ibek/main/user/reference/naming.html>`_
  Conventions for the YAML that ibek consumes.

- `epics-containers documentation <https://epics-containers.github.io>`_
  Documentation and tutorials for the epics-containers suite of tools.

The command line interface for ibek is as follows. The most up to date version
of this can be found by running ``ibek --help``.

.. code-block::

  Usage: ibek [OPTIONS] COMMAND [ARGS]...

  IOC Builder for EPICS and Kubernetes
  Provides support for building generic EPICS IOC container images and for running IOC instances
  in a Kubernetes cluster.

  ╭─ Options ─────────────────────────────────────────────────────────────────────────────────────╮
  │ --version                     Print the version of ibek and exit                              │
  │ --install-completion          Install completion for the current shell.                       │
  │ --show-completion             Show completion for the current shell, to copy it or customize  │
  │                               the installation.                                               │
  │ --help                        Show this message and exit.                                     │
  ╰───────────────────────────────────────────────────────────────────────────────────────────────╯
  ╭─ Commands ────────────────────────────────────────────────────────────────────────────────────╮
  │ support    Commands for building support modules during container build                       │
  │ ioc        Commands for building generic IOCs during container build                          │
  │ startup    Commands for building IOC instance startup files at container runtime              │
  ╰───────────────────────────────────────────────────────────────────────────────────────────────╯

  Usage: ibek support [OPTIONS] COMMAND [ARGS]...

  Commands for building support modules during container build

  ╭─ Options ─────────────────────────────────────────────────────────────────────────────────────╮
  │ --help          Show this message and exit.                                                   │
  ╰───────────────────────────────────────────────────────────────────────────────────────────────╯
  ╭─ Commands ────────────────────────────────────────────────────────────────────────────────────╮
  │ apt-install         Install debian packages into the container. If they have an http:// or    │
  │                     https:// prefix then they will be downloaded and installed from file.     │
  │ git-clone           clone a support module from a remote repository                           │
  │ register            prepare the configure RELEASE files to build a support module inside an   │
  │                     epics-containers build                                                    │
  │ add-libs            declare the libraries for this support module for inclusion in IOC        │
  │                     Makefile                                                                  │
  │ add-dbds            declare the dbd files for this support module for inclusion in IOC        │
  │                     Makefile                                                                  │
  │ add-release-macro   add or replace a macro the global RELEASE file                            │
  │ add-config-macro    add or replace a macro in CONFIG_SITE.linux-x86_64.Common file            │
  │ add-to-config-site  add some text to a support module's CONFIG_SITE file                      │
  │ compile             compile a support module after preparation with `ibek support register`   │
  │                     etc.                                                                      │
  │ generate-links      generate symlinks to the bob, pvi and support YAML for a compiled IOC     │
  │ generate-schema     Produce JSON global schema for all <support_module>.ibek.support.yaml     │
  │                     files                                                                     │
  ╰───────────────────────────────────────────────────────────────────────────────────────────────╯

  Usage: ibek ioc [OPTIONS] COMMAND [ARGS]...

  Commands for building generic IOCs during container build

  ╭─ Options ─────────────────────────────────────────────────────────────────────────────────────╮
  │ --help          Show this message and exit.                                                   │
  ╰───────────────────────────────────────────────────────────────────────────────────────────────╯
  ╭─ Commands ────────────────────────────────────────────────────────────────────────────────────╮
  │ generate-makefile  get the dbd and lib files from all support modules and generate            │
  │                    iocApp/src/Makefile from iocApp/src/Makefile.jinja                         │
  │ compile            Compile a generic IOC after support modules are registered and compiled    │
  │ build              EXPERIMENTAL: Attempt to interpret the Dockerfile and run it's commands    │
  │                    inside the devcontainer. For internal, incremental builds of the           │
  │                    Dockerfile.                                                                │
  │ generate-schema    Create a json schema from a number of support_module.ibek.support.yaml     │
  │                    files                                                                      │
  ╰───────────────────────────────────────────────────────────────────────────────────────────────╯

  Usage: ibek startup [OPTIONS] COMMAND [ARGS]...

  Commands for building IOC instance startup files at container runtime

  ╭─ Options ─────────────────────────────────────────────────────────────────────────────────────╮
  │ --help          Show this message and exit.                                                   │
  ╰───────────────────────────────────────────────────────────────────────────────────────────────╯
  ╭─ Commands ────────────────────────────────────────────────────────────────────────────────────╮
  │ generate          Build a startup script for an IOC instance                                  │
  ╰───────────────────────────────────────────────────────────────────────────────────────────────╯

.. |code_ci| image:: https://github.com/epics-containers/ibek/actions/workflows/code.yml/badge.svg?branch=change_linter_to_ruff
    :target: https://github.com/epics-containers/ibek/actions/workflows/code.yml
    :alt: Code CI

.. |docs_ci| image:: https://github.com/epics-containers/ibek/actions/workflows/docs.yml/badge.svg?branch=change_linter_to_ruff
    :target: https://github.com/epics-containers/ibek/actions/workflows/docs.yml
    :alt: Docs CI

.. |coverage| image:: https://codecov.io/gh/epics-containers/ibek/branch/change_linter_to_ruff/graph/badge.svg
    :target: https://codecov.io/gh/epics-containers/ibek
    :alt: Test Coverage

.. |pypi_version| image:: https://img.shields.io/pypi/v/ibek.svg
    :target: https://pypi.org/project/ibek
    :alt: Latest PyPI version

.. |black| image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black

.. |license| image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg
    :target: https://opensource.org/licenses/Apache-2.0
    :alt: Apache License

..
    Anything below this line is used when viewing README.rst and will be replaced
    when included in index.rst

See https://epics-containers.github.io/ibek for current documentation.
