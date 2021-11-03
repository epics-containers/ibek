#!/bin/bash

# this script regenerates the files used in tests
# it is useful after making changes to the code that affect the schemas etc.
#
# please bear in mind that this is cheating tests! It requires visual
# verifiction of the files in the samples folders after running.
#

export SAMPLES_DIR=$(realpath $(dirname "${BASH_SOURCE[0]}"))

# this is so relative schema mode lines work
cd $SAMPLES_DIR

echo making the global schema
pipenv run ibek ibek-schema ${SAMPLES_DIR}/schemas/ibek.schema.json

echo making the epics definition schema
pipenv run ibek ioc-schema ${SAMPLES_DIR}/yaml/epics.ibek.yaml $SAMPLES_DIR/schemas/epics.schema.json
echo making the pmac support module definition schema
pipenv run ibek ioc-schema ${SAMPLES_DIR}/yaml/pmac.ibek.yaml $SAMPLES_DIR/schemas/pmac.schema.json
echo making the asyn support module definition schema
pipenv run ibek ioc-schema ${SAMPLES_DIR}/yaml/asyn.ibek.yaml $SAMPLES_DIR/schemas/asyn.schema.json
echo making a container definition schema
pipenv run ibek ioc-schema ${SAMPLES_DIR}/yaml/asyn.ibek.yaml ${SAMPLES_DIR}/yaml/pmac.ibek.yaml $SAMPLES_DIR/schemas/container.schema.json
echo making a schema for bl45p-mo-ioc-04
pipenv run ibek ioc-schema ${SAMPLES_DIR}/yaml/{epics,pmac}.ibek.yaml $SAMPLES_DIR/schemas/bl45p-mo-ioc-04.schema.json

# add --no-schema if needed (but above line should ensure that it is correct)
echo making helm files
pipenv run ibek build-helm ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-02.pmac.yaml /tmp/ioc
cp /tmp/ioc/bl45p-mo-ioc-02/values.yaml ${SAMPLES_DIR}/helm/
cp /tmp/ioc/bl45p-mo-ioc-02/Chart.yaml ${SAMPLES_DIR}/helm/

echo making startup script
pipenv run ibek build-startup ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-02.pmac.yaml ${SAMPLES_DIR}/yaml/pmac.ibek.yaml /tmp/ioc/ioc.boot
cp /tmp/ioc/ioc.boot ${SAMPLES_DIR}/helm/
echo making multiple support module startup script
pipenv run ibek build-startup ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-03.pmac.yaml ${SAMPLES_DIR}/yaml/pmac.ibek.yaml ${SAMPLES_DIR}/yaml/asyn.ibek.yaml /tmp/ioc/ioc.boot
cp /tmp/ioc/ioc.boot ${SAMPLES_DIR}/helm/bl45p-mo-ioc-03.boot
