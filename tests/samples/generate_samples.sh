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
ibek ibek-schema ${SAMPLES_DIR}/schemas/ibek.defs.schema.json

echo making the epics definition schema
ibek ioc-schema ${SAMPLES_DIR}/yaml/epics.ibek.defs.yaml $SAMPLES_DIR/schemas/epics.ibek.defs.schema.json
echo making the pmac support module definition schema
ibek ioc-schema ${SAMPLES_DIR}/yaml/pmac.ibek.defs.yaml $SAMPLES_DIR/schemas/pmac.ibek.entities.schema.json
echo making the asyn support module definition schema
ibek ioc-schema ${SAMPLES_DIR}/yaml/asyn.ibek.defs.yaml $SAMPLES_DIR/schemas/asyn.ibek.entities.schema.json
echo making a container definition schema
ibek ioc-schema ${SAMPLES_DIR}/yaml/asyn.ibek.defs.yaml ${SAMPLES_DIR}/yaml/pmac.ibek.defs.yaml $SAMPLES_DIR/schemas/container.ibek.entities.schema.json
echo making a schema for bl45p-mo-ioc-04
ibek ioc-schema ${SAMPLES_DIR}/yaml/{epics,pmac}.ibek.defs.yaml $SAMPLES_DIR/schemas/bl45p-mo-ioc-04.ibek.entities.schema.json

# add --no-schema if needed (but above line should ensure that it is correct)
echo making helm files
ibek build-helm ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-02.ibek.entities.yaml /tmp/ioc
cp /tmp/ioc/bl45p-mo-ioc-02/values.yaml ${SAMPLES_DIR}/helm/
cp /tmp/ioc/bl45p-mo-ioc-02/Chart.yaml ${SAMPLES_DIR}/helm/

echo making startup script
ibek build-startup ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-02.ibek.entities.yaml ${SAMPLES_DIR}/yaml/pmac.ibek.defs.yaml --out /tmp/ioc/ioc.boot --db-out /tmp/ioc/make_db.sh
cp /tmp/ioc/ioc.boot ${SAMPLES_DIR}/helm/
echo making bl45p-mo-ioc-03.boot
ibek build-startup ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-03.ibek.entities.yaml ${SAMPLES_DIR}/yaml/pmac.ibek.defs.yaml ${SAMPLES_DIR}/yaml/asyn.ibek.defs.yaml --out /tmp/ioc/ioc.boot --db-out /tmp/ioc/make_db.sh
cp /tmp/ioc/ioc.boot ${SAMPLES_DIR}/helm/bl45p-mo-ioc-03.boot
echo making bl45p-mo-ioc-04.boot
ibek build-startup ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-04.ibek.entities.yaml ${SAMPLES_DIR}/yaml/{epics,pmac}.ibek.defs.yaml --out /tmp/ioc/ioc.boot --db-out /tmp/ioc/make_db.sh
cp /tmp/ioc/ioc.boot ${SAMPLES_DIR}/helm/bl45p-mo-ioc-04.boot
