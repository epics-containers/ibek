#!/bin/bash

# this script regenerates the files used in tests
# it is useful after making changes to the code that affect the schemas etc.
#
# please bear in mind that this is cheating tests! It requires visual
# verifiction of the files in the samples folders after running.
#

export SAMPLES_DIR=$(dirname "${BASH_SOURCE[0]}")

echo making the global schema
pipenv run ibek ibek-schema ${SAMPLES_DIR}/schemas/ibek.schema.json

echo making the pmac support module definition schema
pipenv run ibek ioc-schema ${SAMPLES_DIR}/yaml/pmac.ibek.yaml $SAMPLES_DIR/schemas/pmac.schema.json

echo making helm files
pipenv run ibek build-ioc ${SAMPLES_DIR}/yaml/pmac.ibek.yaml ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-02.pmac.yaml /tmp/ioc
cp /tmp/ioc/bl45p-mo-ioc-02/config/ioc.boot ${SAMPLES_DIR}/helm/
cp /tmp/ioc/bl45p-mo-ioc-02/values.yaml ${SAMPLES_DIR}/helm/
cp /tmp/ioc/bl45p-mo-ioc-02/Chart.yaml ${SAMPLES_DIR}/helm/

echo making sample pmac defintiion object
pipenv run ibek dump-support tests/samples/yaml/pmac.ibek.yaml
cat ${SAMPLES_DIR}/black/preamble /tmp/support.py > ${SAMPLES_DIR}/classes/pmac_support.py
cd ${SAMPLES_DIR}/black
pipenv run black --experimental-string-processing ${SAMPLES_DIR}/classes
