Support YAML Conventions
========================

TODO: Create a linter that checks for these conventions
TODO: split out ibek-defs and ibek-defs-dls for internal support modules.

IBEK Support YAML defines what Entities can be instantiated
by IOC instances.
There will be one of these YAML files per support module.
These files should adhere to the following naming conventions.

Filename
--------

The filename is always *SupportModule*.ibek.support.yaml, where
*SupportModule* is the name of the support module as named in its git
repository.

The file should be stored in the ibek-defs repository in a folder with
name *SupportModule*. These folders should be located in the root of the
repository.

*SupportModule* should use the same case as the git repo.

e.g.

.. code-block:: text

    ADCore/ADCore.ibek.support.yaml
    pmac/pmac.ibek.support.yaml
    aravisGigE/aravisGigE.ibek.support.yaml

Module
------

Every YAML file will start by declaring the module name using ``module:``.
This should typically
be the same as the filename prefix. However if the filename prefix is not a
a legal python name it can be adjusted to make it legal. This would usually
mean replacing '-' with '_'.

.. code-block:: text

    ADCore
    pmac
    aravisGigE

Definitions
-----------

All definitions have a ``name:`` field. This should be UpperCamelCase as it
represents a class in Python.

Args
----

Every Arg also has a name and these should be snake_case as they represent
class properties in Python.

HOWEVER: where these arguments refer to a database template macro, the original
name should be used. This means that no changes are required in the templates
in order to support the include_args feature.

ADDITIONAL: because the above caveat breaks the naming convention. We will
maintain the historical naming from builder.py where support module has this
historical support.

SUMMARY: only new modules will use the snake_case naming convention. Others
will use the historical adhoc naming conventions.

Functions
---------

Function Arguments should be in UpperCamelCase. Function names must be as
per the function name you are calling in iocShell startup.

e.g.

.. code-block:: yaml

    script:
      - type: function
        name: pscAddIpModule
        header: |
          # Add IP module
        args:
          CarrierId: $({{ carrier.name }})
          IpSiteNumber: "{{ ip_site_number }}"
          Vector: "$({{ interrupt_vector.name }})"
          Links: "{{ links }}"
