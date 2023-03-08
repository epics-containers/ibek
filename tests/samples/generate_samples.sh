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
ibek ioc-schema ${SAMPLES_DIR}/yaml/epics.ibek.support.yaml $SAMPLES_DIR/schemas/epics.ibek.support.schema.json
echo making the pmac support module definition schema
ibek ioc-schema ${SAMPLES_DIR}/yaml/pmac.ibek.support.yaml $SAMPLES_DIR/schemas/pmac.ibek.entities.schema.json
echo making the asyn support module definition schema
ibek ioc-schema ${SAMPLES_DIR}/yaml/asyn.ibek.support.yaml $SAMPLES_DIR/schemas/asyn.ibek.entities.schema.json
echo making a container definition schema
ibek ioc-schema ${SAMPLES_DIR}/yaml/asyn.ibek.support.yaml ${SAMPLES_DIR}/yaml/pmac.ibek.support.yaml $SAMPLES_DIR/schemas/container.ibek.entities.schema.json
echo making a schema for bl45p-mo-ioc-04
ibek ioc-schema ${SAMPLES_DIR}/yaml/{epics,pmac}.ibek.support.yaml $SAMPLES_DIR/schemas/bl45p-mo-ioc-04.ibek.entities.schema.json

echo making bl45p-mo-ioc-02
ibek build-startup ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-02.ibek.entities.yaml ${SAMPLES_DIR}/yaml/pmac.ibek.support.yaml --out /tmp/ioc/st.cmd --db-out /tmp/ioc/make_db.sh
cp /tmp/ioc/st.cmd ${SAMPLES_DIR}/boot_scripts/
echo making bl45p-mo-ioc-03
ibek build-startup ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-03.ibek.entities.yaml ${SAMPLES_DIR}/yaml/pmac.ibek.support.yaml ${SAMPLES_DIR}/yaml/asyn.ibek.support.yaml --out /tmp/ioc/st.cmd --db-out /tmp/ioc/make_db.sh
cp /tmp/ioc/st.cmd ${SAMPLES_DIR}/boot_scripts/stbl45p-mo-ioc-03
echo making bl45p-mo-ioc-04
ibek build-startup ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-04.ibek.entities.yaml ${SAMPLES_DIR}/yaml/{epics,pmac}.ibek.support.yaml --out /tmp/ioc/st.cmd --db-out /tmp/ioc/make_db.sh
cp /tmp/ioc/st.cmd ${SAMPLES_DIR}/boot_scripts/stbl45p-mo-ioc-04
