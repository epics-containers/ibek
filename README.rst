ibek
===========================

|code_ci| |docs_ci| |coverage| |pypi_version| |license|

IOC Builder for EPICS and Kubernetes:

- In an EPICS support module describe what entities an IOC using it can create,
  what arguments they take, and what database and st.cmd snippets it should
  generate in a ``builder.yaml`` file
- Build support modules together in a container image and use ``ibek`` in the
  image to create a JSON schema of what an IOC using that image can contain
- Write an ``ioc.yaml`` file against that schema listing instances of the
  entities with arguments
- Use ``ibek`` to generate a startup script and database that runs
  up the IOC contained in the image with them

============== ==============================================================
PyPI           ``pip install ibek``
Source code    https://github.com/epics-containers/ibek
Documentation  https://epics-containers.github.io/ibek
Releases       https://github.com/epics-containers/ibek/releases
============== ==============================================================

TODO
----

This project is approaching completion. The following items are still to do:

    from ibek import __version__

    print(f"Hello ibek {__version__}")

    - DONE: Add ability to define embedded objects e.g. AsynIp and AsynSerial would
      both be defined by embedding AsynPort (so similar to how original builder.py
      works)

    $ python -m ibek --version

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

.. |license| image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg
    :target: https://opensource.org/licenses/Apache-2.0
    :alt: Apache License

..
    Anything below this line is used when viewing README.rst and will be replaced
    when included in index.rst

See https://epics-containers.github.io/ibek for more detailed documentation.
