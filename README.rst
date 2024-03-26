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

UPDATE: Version 2.0.0
=====================

There have been a number of breaking changes since version 1.8.0. These are
primarily to support RTEMS cross compiled IOCs. But we have also taken the
opportunity to clarify the CLI.

All changes are compatible with 2.0.0 of ibek-support and 3.4.0 of all other
epics-containers repos. When using ioc-template 3.4.0 to update your generic
IOCs, make sure you also update the ibek-support submodule to 2.0.0 or newer,
then you should have all compatible versions.

--------------------------------------------------------------------------------


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

  [container][~]$ ibek --help
  Usage: ibek [OPTIONS] COMMAND [ARGS]...

    IOC Builder for EPICS and Kubernetes

    Provides support for building generic EPICS IOC container images and for
    running IOC instances in a Kubernetes cluster.

  Options:
    --version                       Print the version of ibek and exit
    --install-completion [bash|zsh|fish|powershell|pwsh]
                                    Install completion for the specified shell.
    --show-completion [bash|zsh|fish|powershell|pwsh]
                                    Show completion for the specified shell, to
                                    copy it or customize the installation.
    --help                          Show this message and exit.

  Commands:
    support  Commands for building support modules during container build
    ioc      Commands for building generic IOCs during container build
    runtime  Commands for building IOC instance startup files at container...
  [container][~]$ ibek support --help
  Usage: ibek support [OPTIONS] COMMAND [ARGS]...

    Commands for building support modules during container build

  Options:
    --help  Show this message and exit.

  Commands:
    apt-install         Install debian packages into the container.
    git-clone           clone a support module from a remote repository
    register            prepare the configure RELEASE files to build a...
    add-libs            declare the libraries for this support module for...
    add-dbds            declare the dbd files for this support module for...
    add-release-macro   add or replace a macro the global RELEASE file
    add-config-macro    add or replace a macro in...
    add-to-config-site  add some text to a support module's CONFIG_SITE file
    compile             compile a support module after preparation with...
    generate-links      generate symlinks to the bob, pvi and support YAML...
    generate-schema     Produce JSON global schema for all...
  [container][~]$ ibek ioc --help
  Usage: ibek ioc [OPTIONS] COMMAND [ARGS]...

    Commands for building generic IOCs during container build

  Options:
    --help  Show this message and exit.

  Commands:
    build-docker            EXPERIMENTAL: Attempt to interpret the...
    generate-schema         Create a json schema from a number of...
    extract-runtime-assets  Find all the runtime assets in an EPICS...
    make-source-template    Create a new IOC boilerplate source tree in the...
    generate-makefile       get the dbd and lib files from all support...
    compile                 Compile a generic IOC after support modules are...
    build                   A convenience function that calls...
  [container][~]$ ibek runtime --help
  Usage: ibek runtime [OPTIONS] COMMAND [ARGS]...

    Commands for building IOC instance startup files at container runtime

  Options:
    --help  Show this message and exit.

  Commands:
    generate  Build a startup script for an IOC instance


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
