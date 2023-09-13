#!/bin/bash

# this script regenerates the files used in tests
# it is useful after making changes to the code that affect the schemas etc.
#
# please bear in mind that this is cheating tests! It requires visual
# verifiction of the files in the samples folders after running.
#

export SAMPLES_DIR=$(realpath $(dirname "${BASH_SOURCE[0]}"))/samples


# this is so relative schema mode lines work
cd $SAMPLES_DIR
mkdir -p schemas
mkdir -p outputs

set -x
echo making the support yaml schema
ibek ibek-schema schemas/ibek.support.schema.json

echo making an ioc schema using object support yaml
ibek ioc-schema yaml/objects.ibek.support.yaml schemas/objects.ibek.ioc.schema.json

echo making an ioc schema using utils support yaml
ibek ioc-schema yaml/utils.ibek.support.yaml schemas/utils.ibek.ioc.schema.json

echo making an ioc schema using multiple support yaml files
ibek ioc-schema yaml/objects.ibek.support.yaml yaml/all.ibek.support.yaml schemas/multiple.ibek.ioc.schema.json

echo making ioc based on objects support yaml
ibek build-startup yaml/objects.ibek.ioc.yaml yaml/objects.ibek.support.yaml --out outputs/objects.st.cmd --db-out outputs/objects.db.subst

echo making ioc based on utils support yaml
ibek build-startup yaml/utils.ibek.ioc.yaml yaml/utils.ibek.support.yaml --out outputs/utils.st.cmd --db-out outputs/utils.db.subst

echo making ioc based on mutiple support yaml
ibek build-startup yaml/all.ibek.ioc.yaml yaml/objects.ibek.support.yaml yaml/all.ibek.support.yaml --out outputs/all.st.cmd --db-out outputs/all.db.subst
