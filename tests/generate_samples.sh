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

echo making an ioc schema using multiple support yaml files
ibek ioc-schema yaml/objects.ibek.support.yaml yaml/all.ibek.support.yaml schemas/multiple.ibek.ioc.schema.json

# echo making ioc based on objects support yaml
ibek build-startup yaml/objects.ibek.ioc.yaml yaml/objects.ibek.support.yaml --out outputs/objects.st.cmd --db-out outputs/objects.make_db.sh

# echo making ioc based on mutiple support yaml
ibek build-startup yaml/all.ibek.ioc.yaml yaml/objects.ibek.support.yaml yaml/all.ibek.support.yaml --out outputs/all.st.cmd --db-out outputs/all.make_db.sh


# echo making the global ioc schema using all support yaml in ibek-defs
# ibek ioc-schema ./*/*.ibek.support.yaml ${SAMPLES_DIR}/schemas/all.ibek.support.schema.json



# echo making the epics definition schema
# ibek ioc-schema ${DEFS}/_global/epics.ibek.support.yaml $SAMPLES_DIR/schemas/epics.ibek.support.schema.json
# echo making the pmac support module definition schema
# ibek ioc-schema ${DEFS}/pmac/pmac.ibek.support.yaml $SAMPLES_DIR/schemas/pmac.ibek.entities.schema.json
# echo making the asyn support module definition schema
# ibek ioc-schema ${DEFS}/asyn/asyn.ibek.support.yaml $SAMPLES_DIR/schemas/asyn.ibek.entities.schema.json
# echo making a container definition schema
# ibek ioc-schema ${DEFS}/asyn/asyn.ibek.support.yaml ${DEFS}/pmac/pmac.ibek.support.yaml $SAMPLES_DIR/schemas/container.ibek.entities.schema.json
# echo making a schema for bl45p-mo-ioc-04
# ibek ioc-schema ${DEFS}/_global/epics.ibek.support.yaml ${DEFS}/pmac/pmac.ibek.support.yaml $SAMPLES_DIR/schemas/bl45p-mo-ioc-04.ibek.entities.schema.json

# echo making bl45p-mo-ioc-02
# ibek build-startup ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-02.ibek.ioc.yaml ${DEFS}/pmac/pmac.ibek.support.yaml --out /tmp/ioc/st.cmd --db-out /tmp/ioc/make_db.sh
# cp /tmp/ioc/st.cmd ${SAMPLES_DIR}/boot_scripts/
# echo making bl45p-mo-ioc-03
# ibek build-startup ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-03.ibek.ioc.yaml ${DEFS}/pmac/pmac.ibek.support.yaml ${DEFS}/asyn/asyn.ibek.support.yaml --out /tmp/ioc/st.cmd --db-out /tmp/ioc/make_db.sh
# cp /tmp/ioc/st.cmd ${SAMPLES_DIR}/boot_scripts/stbl45p-mo-ioc-03
# echo making bl45p-mo-ioc-04
# ibek build-startup ${SAMPLES_DIR}/yaml/bl45p-mo-ioc-04.ibek.ioc.yaml ${DEFS}/_global/epics.ibek.support.yaml ${DEFS}/pmac/pmac.ibek.support.yaml --out /tmp/ioc/st.cmd --db-out /tmp/ioc/make_db.sh
# cp /tmp/ioc/st.cmd ${SAMPLES_DIR}/boot_scripts/stbl45p-mo-ioc-04
# echo making test-ioc
# ibek build-startup ${SAMPLES_DIR}/example-ibek-config/ioc.yaml ${DEFS}/_global/epics.ibek.support.yaml ${DEFS}/_global/devIocStats.ibek.support.yaml --out /tmp/ioc/st.cmd --db-out /tmp/ioc/make_db.sh
# cp /tmp/ioc/st.cmd ${SAMPLES_DIR}/boot_scripts/test.ioc.cmd
# cp /tmp/ioc/make_db.sh ${SAMPLES_DIR}/boot_scripts/test.ioc.make_db.sh

# echo making SR-RF-IOC-08 IOC
# ibek build-startup ${SAMPLES_DIR}/example-srrfioc08/SR-RF-IOC-08.ibek.ioc.yaml ${DEFS}/*/*.support.yaml --out /tmp/ioc/st.cmd --db-out /tmp/ioc/make_db.sh
# cp /tmp/ioc/st.cmd ${SAMPLES_DIR}/example-srrfioc08
# cp /tmp/ioc/make_db.sh ${SAMPLES_DIR}/example-srrfioc08

# echo making values_test IOC
# ibek build-startup ${SAMPLES_DIR}/values_test/values.ibek.ioc.yaml ${DEFS}/*/*.support.yaml --out /tmp/ioc/st.cmd --db-out /tmp/ioc/make_db.sh
# cp /tmp/ioc/st.cmd ${SAMPLES_DIR}/values_test

# PYDANTIC_DIR=${SAMPLES_DIR}/pydantic
# cd $PYDANTIC_DIR

# echo making the support yaml schema
# ibek ibek-schema ${PYDANTIC_DIR}/../schemas/ibek.defs.schema.json

# echo making the pydantic test definition schema
# ibek ioc-schema ${PYDANTIC_DIR}/test.ibek.support.yaml $PYDANTIC_DIR/test.ibek.ioc.schema.json

# echo making the pydantic test ioc startup script
# ibek build-startup ${PYDANTIC_DIR}/test.ibek.ioc.yaml ${PYDANTIC_DIR}/test.ibek.support.yaml --out $PYDANTIC_DIR/st.cmd --db-out $PYDANTIC_DIR/make_db.sh




