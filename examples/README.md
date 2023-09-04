Intro
=====

These example scripts are used to investigate an issue with error reporting in ibek.

They also serve as a good minimal example of how to do object references within a pydantic 2 model.

The incrementing numeric suffix represents a progression from the most simple possible example of a pydantic model with a reference to a more complex example that more closely resembles ibek's approach which dynamically creates the Entity classes.

In the yaml subfolder is a support module yaml and IOC yaml that will make ibek load a very similar model to that described in these test scripts.

Issue under investigation
=========================

The issue is that when an object refers to another object then the error reported is that the offending object's id cannot be found. This masks the underlying schema issue which is what should be reported first. The custom field validator created in make_entity_model seems to be throwing the error before the schema validation issue is reported.

At present for the incorrect schema in entity e1 ibek reports:

```
KeyError: 'object one not found in []'
```

And test_refs1.py reports

```
Extra inputs are not permitted [type=extra_forbidden, input_value='bad argument', input_type=str]
```

The latter is the useful error that points you at the root cause.

Example Issue
=============

The test_refs1.py demonstrates the issue

I've posted a discussion on the subject here
https://github.com/pydantic/pydantic/discussions/6731

Resolution
==========

Resolved here https://github.com/pydantic/pydantic/issues/7304

Simply Throw a ValueError instead of a KeyError in the custom validator.
