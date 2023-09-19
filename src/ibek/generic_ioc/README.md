Package Naming
==============

This sub-package contains the additional modules required at the container
build stage. Such functions are concerned with building support modules
and generic IOCs that depend on them.

The root package in ibek contains the modules that are concerned with
generating IOC instances. They generate the startup script and database
substitution files for each IOC instance. They also are concerned with
the JSON schema's that assist in the specification of IOC instance.

Historically ibek was a single package with the latter functions only.
At present I've left the original package in the root to avoid making the
git history difficult to follow. TODO review package structure.
