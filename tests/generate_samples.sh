#!/bin/bash

# this script regenerates the files used in tests
# it is useful after making changes to the code that affect the schemas etc.
#
# please bear in mind that this is cheating tests! It requires visual
# verifiction of the files in the samples folders after running.
#

export SAMPLES_DIR=$(realpath $(dirname "${BASH_SOURCE[0]}"))/samples

export EPICS_ROOT=${SAMPLES_DIR}/epics

# this is so relative schema mode lines work
cd $SAMPLES_DIR
mkdir -p schemas
mkdir -p outputs

set -ex

mkdir -p epics/pvi-defs
cp yaml/simple.pvi.device.yaml  epics/pvi-defs/simple.pvi.device.yaml

echo making the support yaml schema
ibek support generate-schema --output schemas/ibek.support.schema.json

echo making an ioc schema using object support yaml
ibek ioc generate-schema yaml/objects.ibek.support.yaml --output schemas/objects.ibek.ioc.schema.json

echo making an ioc schema using utils support yaml
ibek ioc generate-schema yaml/utils.ibek.support.yaml --output schemas/utils.ibek.ioc.schema.json

echo making an ioc schema using multiple support yaml files
ibek ioc generate-schema yaml/objects.ibek.support.yaml yaml/all.ibek.support.yaml --output schemas/multiple.ibek.ioc.schema.json

echo making ioc based on objects support yaml
ibek runtime generate yaml/objects.ibek.ioc.yaml yaml/objects.ibek.support.yaml --out outputs/objects.st.cmd --db-out outputs/objects.ioc.subst

echo making ioc based on utils support yaml
ibek runtime generate yaml/utils.ibek.ioc.yaml yaml/utils.ibek.support.yaml --out outputs/utils.st.cmd --db-out outputs/utils.ioc.subst

echo making ioc based on mutiple support yaml
ibek runtime generate yaml/all.ibek.ioc.yaml yaml/objects.ibek.support.yaml yaml/all.ibek.support.yaml --out outputs/all.st.cmd --db-out outputs/all.ioc.subst
cp epics/opi/* outputs/
