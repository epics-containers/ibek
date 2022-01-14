ibek
====

|code_ci| |docs_ci| |coverage| |pypi_version| |license|

IOC Builder for EPICS and Kubernetes:

- In an EPICS support module describe what entities an IOC using it can create,
  what arguments they take, and what database and st.cmd snippets it should
  generate in a ``builder.yaml`` file
- Build support modules together in a container image and use ``ibek`` in the
  image to create a JSON schema of what an IOC using that image can contain
- Write an ``ioc.yaml`` file against that schema listing instances of the
  entities with arguments
- Use ``ibek`` to generate a startup script, database and Helm chart that runs
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

    - Complete documentation in general

    - Add a diagram and more details. Use draw.io for image, and save as SVG
      with source embed in it, save as something.draw.io.svg

    - Add ability to define embedded objects e.g. AsynIp and AsynSerial would
      both be defined by embedding AsynPort (so similar to how original builder.py
      works)

    - Add support for enums where you define the possible values inline

    - update helm-template/config/start.sh to call 'ibek build-startup' when it
      sees a ioc.boot.yaml file in the startup directory. This change requires
      embedding ibek into the epics-base container image.

.. |code_ci| image:: https://github.com/epics-containers/ibek/workflows/Code%20CI/badge.svg?branch=master
    :target: https://github.com/epics-containers/ibek/actions?query=workflow%3A%22Code+CI%22
    :alt: Code CI

.. |docs_ci| image:: https://github.com/epics-containers/ibek/workflows/Docs%20CI/badge.svg?branch=master
    :target: https://github.com/epics-containers/ibek/actions?query=workflow%3A%22Docs+CI%22
    :alt: Docs CI

.. |coverage| image:: https://codecov.io/gh/epics-containers/ibek/branch/master/graph/badge.svg
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
