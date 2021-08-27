.. include:: ../README.rst
    :end-before: when included in index.rst

.. |logo| image:: images/ibek-logo.svg

TODO
----

This project is incomplete. The following items are still to do:

    - Complete documentation in general

    - Add a param no_axes to pmac.Geobrick instead of hardcoding 8

    - update the database entry generation in jinja to make use of the property
      include_args. This should automatically add macro substitutions for
      macros with the same name as the argument (and greatly reduce the length
      of the jinja template for DlsPmacAsynMotor)

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

How the documentation is structured
-----------------------------------

.. rst-class:: columns

:ref:`tutorials`
~~~~~~~~~~~~~~~~

Tutorials for installation, library and commandline usage. New users start here.

.. rst-class:: columns

:ref:`how-to`
~~~~~~~~~~~~~

Practical step-by-step guides for the more experienced user.

.. rst-class:: columns

:ref:`explanations`
~~~~~~~~~~~~~~~~~~~

Explanation of how the library works and why it works that way.

.. rst-class:: columns

:ref:`reference`
~~~~~~~~~~~~~~~~

Technical reference material, for classes, methods, APIs, commands, and contributing to the project.

.. rst-class:: endcolumns

About the documentation
~~~~~~~~~~~~~~~~~~~~~~~

`Why is the documentation structured this way? <https://documentation.divio.com>`_

.. toctree::
    :caption: Tutorials
    :name: tutorials
    :maxdepth: 1

    tutorials/installation

.. toctree::
    :caption: How-to Guides
    :name: how-to
    :maxdepth: 1

    how-to/edit_yaml

.. toctree::
    :caption: Explanations
    :name: explanations
    :maxdepth: 1

    explanations/entities

.. rst-class:: no-margin-after-ul

.. toctree::
    :caption: Reference
    :name: reference
    :maxdepth: 1

    reference/api
    reference/contributing

* :ref:`genindex`
