IOC Builder Support Module Converter for ibek
=============================================

This tool will inspect a DLS support module with ioc builder support. It then
creates a ibek <module>.ibek.support.yaml file for use in epics-containers.
This provides an easy transition for support modules from DLS IOC
builder to the epics-containers.

The tool works by loading etc/builder.py and instantiating an instance of
each of the classes defined in that file. It then inspects the resulting
object to determine what it would have done when being used to generate
a traditional DLS IOC.

In order to do this, the tool needs make a best guess at the set of arguments
to pass to each class constructor. In some cases the guesses will not
be compatible with the code in builder.py. For example if a string value
from a DB is converted to an int then it is important for that string value
to be a valid int and there is no easy way to guess that this is required.

In order to cope with poor guesses for argument values, the tool will print
out all the objects it instantiates and t he arguments it passes to them. Every
argument is numbered. The user can override the argument passed using the
--override (-o) flag. The override argument is a space separated list of
ARGUMENT_NO:VALUE pairs. For example this is the command that works with a
recent version of the pmac module:

```bash
./builder2ibek.support.py /dls_sw/prod/R3.14.12.7/support/pmac/2-5-23beta1/ -o '14:A+B 474:A+B 801:1 805:1.0 804:1.0'
```

Without the 3 overrides the tools will fail as builder.py tries to convert
these 3 args to int.

