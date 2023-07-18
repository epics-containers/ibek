#!/bin/bash

# This script runs tests against ibek that use the same set of objects
# employed by the test_refsX.py scripts in the above folder.
# It demonstrates that unline the above scripts ibek gets the wrong error
#    KeyError: 'object one not found in []'
# when it should get
#    Extra inputs are not permitted [type=extra_forbidden, input_value='bad argument', input_type=str]

ibek ioc-schema test.ibek.support.yaml test.ibek.ioc.schema.json
ibek build-startup test.ibek.ioc.yaml test.ibek.support.yaml
