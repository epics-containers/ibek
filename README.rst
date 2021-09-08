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
Changelog      https://github.com/epics-containers/ibek/blob/master/CHANGELOG.rst
============== ==============================================================

TODO
----

This project is incomplete. The following items are still to do:

    - Complete documentation in general

    - Break out Helm Chart generation and boot script generation into two
      separate commands:

      - build-helm will make a helm chart which just has the ioc instance yaml
        in its config folder. This is to be run outside of the container to
        make the helm chart

      - make-boot will generate an ioc.boot from an instance yaml and this
        will run inside the container at ioc startup and hence have access to
        all the needed <support>.ibek.yaml definition files.

      - this will require changes to start.sh to support converting yaml to
        ioc.boot but should also continue to support a native ioc.boot for
        non ibek users.

      - The CI will be responsible for making a schema file from all of the
        <support>.ibek.yaml definition files and publishing it as a repository
        artifact on github. This means that editors will be able to make use
        of the schema for preparing IOC instance entity files.

    - finally support for multiple support definition files is required at
      present the cli only takes a single support definition file. All these
      commands need to support multiple definition files for the whole container.

        - make-script
        - make-helm
        - ioc-schema

    - this will require an additional class to represent a container as a set
      of support modules.

    - Add a diagram and more details. Use draw.io for image, and save as SVG
      with source embed in it, save as something.draw.io.svg

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
