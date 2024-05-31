.. _entities:

Modules, Definitions and Entities
=================================

This page is a top down explanation of the above key terms by referencing the
example IOC instance bl45p-mo-ioc-02 used in the system tests for this
project.

The explanations rely on an understanding of the difference between
generic IOCs and IOC instances. See
`Generic IOCs and instances <https://epics-containers.github.io/main/explanations/introduction.html#generic-iocs-and-instances>`_.

Modules
-------

Every generic IOC image will include a number of EPICS support modules.

The bl45p-mo-ioc-02 ioc instance example uses the generic IOC container image
`ioc-pmac <https://github.com/epics-containers/ioc-pmac>`_ . This image
contains the support modules pmac and motor plus the common support modules
from `epics-modules <https://github.com/epics-containers/epics-modules>`_

Each IOC instance will mount a generic IOC image and therefore be able to make
use of the libraries and DB templates in any of those support modules.

The goal of ibek is to allow a developer to define an instance of an IOC and
make use of functions of its support modules.

ibek uses a **support module definition file** to determine what
features of a support module may be instantiated.

Hence there is a collection of **support module definition files**
inside of each generic IOC.

In the code the class GenericIoc is used to represent a generic IOC and an
instance of that class represent an IOC instance.

Definition
----------

Each support module has its own **support module definition file** . This
is a YAML file whose name is by convention ``<support_module>.ibek.support.yaml``

These will all reside in a folder called /ibek in the container
image.

The **support module definition file** contains **Definitions** which
determine what **Entities** an IOC instance may instantiate.

For example the pmac support module declares the following **Definitions**
in ``pmac.ibek.support.yaml``
(currently this is limited to 3 - the full implementation would have more):

  - Geobrick

  - DlsPmacAsynIPPort

  - DlsPmacAsynMotor

Each Definition describes a class of Entity by providing:

  - Entity class name

  - a list of arguments to supply when declaring an Entity

  - boot script entries to add for the Entity in the form of a jinja
    template that may refer to the above arguments

  - database templates to instantiate for the Entity with macro values from
    the above arguments


Expand below for the example **support module definition file**:

    .. raw:: html

        <details>
        <summary><a>objects.ibek.support.yaml</a></summary>

    .. include:: ../../../tests/samples/support/motorSim.ibek.support.yaml
        :literal:

    .. raw:: html

        </details>

Definition is implemented in the code using a class of the same name.


Entity
------

ibek can generate an IOC instance using an
**IOC instance entity file**. This is
a YAML file with name of the form ``<ioc_name>.<container>.yaml``.

The **IOC instance entity file** declares the Entities that the IOC
instance requires.

An Entity represents any piece of functionality of an IOC that is
configured through EPICS database and/or startup script.

The classes of Entity that can be instantiated for a given generic IOC are
declared in the Definitions files described above.

Declaring an Entity
for an IOC instance will cause ibek to generate lines in the startup script.
The generated startup script will also supply the EPICS database
entries using dbLoadRecords and database templates.

The example motion IOC instance bl45p-mo-ioc-02 has the following entities:

  - DlsPmacAsynIPPort (one instance)

    - represents a connection to a motion controller

    - configured via

      - pmacAsynIPConfigure in the boot script

  - Geobrick (one instance)

      - represents the motion controller itself

      - configured via

        - pmacCreateController in boot script

        - pmacCreateAxes in the boot script

        - dbLoadRecords of pmacController.template and pmacStatus.template

  - DlsPmacAsynMotor (two instances)

      - represents a single motor connected to the controller

      - configured via:

        - dbLoadRecords of dls_pmac_asyn_motor.template

The example **IOC instance entity file** is shown below along with the st.cmd
file that ibek will generate from it.

Click the arrows to reveal the files.

    .. raw:: html

        <details>
        <summary><a>all.ibek.ioc.yaml</a></summary>

    .. include:: ../../../tests/samples/iocs/motorSim.ibek.ioc.yaml
        :literal:

    .. raw:: html

        </details>
        <details>
        <summary><a>st.cmd</a></summary>

    .. include:: ../../../tests/samples/outputs/motorSim/st.cmd
        :literal:

    .. raw:: html

        </details>

Entity is implemented in the code using a class of the same name.

Schemas
-------

The YAML files described above are constrained by schemas. These schemas are
available to the developer and may be used to assist in generating the YAML.

Note that the author of an IOC instance needs access to <container>.schema.json
in order to correctly craft a correct <ioc>.<container>.yaml. For this
reason the container schema file is published as a github artifact along with
the release of the container image. All other ibek operations happen within
the container or during container development.

Thus, the sequence of files is as follows:

.. list-table:: Summary of ibek files sequence
    :widths: 5 40 70
    :header-rows: 1

    *   - num
        - Name
        - Description
    *   - 1
        - ibek.defs.schema.json
        - Global Schema for **2**
    *   - 2
        - <support>.ibek.support.yaml
        - Definition file for a support module. Generates part of **3**
    *   - 3
        - <container>.entities.schema.json
        - Schema for **4**. Generated by combining all of **2** from a container
    *   - 4
        - <ioc>.ibek.ioc.yaml
        - Description of Entities for an IOC instance.
    *   - 5
        - IOC Startup Script st.cmd
        - Startup script for booting the IOC

The Global Schema and example IOC instance schema are below:

    .. raw:: html

        <details>
        <summary><a>ibek.support.schema.json</a></summary>

    .. include:: ../../../tests/samples/schemas/ibek.support.schema.json
        :literal:

    .. raw:: html

        </details>
        <details>
        <summary><a>multiple.ibek.ioc.schema.json</a></summary>

    .. include:: ../../../tests/samples/schemas/single.ibek.ioc.schema.json
        :literal:

    .. raw:: html

        </details>

This results in the overall generated file structure:

.. raw:: html
    :file: ../../images/ibek-arch.svg

Commands
--------

The ibek commands to progress through the file sequence above are as follows


.. list-table:: Summary of ibek stages
    :widths: 5 40 70
    :header-rows: 1

    *   - num
        - Name
        - Command
    *   - 1
        - ``ibek.defs.schema.json``
        - ``ibek ibek-schema``
    *   - 2
        - ``<support>.ibek.support.yaml``
        - Hand crafted by the container developer. Held in the container.
    *   - 3
        - ``<container>.ibek.entities.schema.json``
        - ``ibek ioc-schema ...`` run at container build time. ``...``
          == all ``<support>.ibek.support.yaml`` within the container.
    *   - 4
        - ``<ioc>.ibek.ioc.yaml``
        - Hand crafted at IOC instance design time
    *   - 5
        - IOC startup script
        - ``ibek build-startup <ioc>.ibek.ioc.yaml ...``. Run at IOC startup time in the
          container. ``...`` == all ``<support>.ibek.support.yaml`` within the container.



