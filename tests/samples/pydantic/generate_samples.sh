#!/bin/bash

# this script regenerates the files used in tests
# it is useful after making changes to the code that affect the schemas etc.
#
# please bear in mind that this is cheating tests! It requires visual
# verifiction of the files in the samples folders after running.
#

export PYDANTIC_DIR=$(realpath $(dirname "${BASH_SOURCE[0]}"))/
export DEFS=${PYDANTIC_DIR}/../../ibek-defs

# this is so relative schema mode lines work
cd $PYDANTIC_DIR

echo making the support yaml schema
ibek ibek-schema ${PYDANTIC_DIR}/../schemas/ibek.defs.schema.json

echo making the pydantic test definition schema
ibek ioc-schema ${PYDANTIC_DIR}/test.ibek.support.yaml $PYDANTIC_DIR/test.ibek.ioc.schema.json

echo making the pydantic test ioc startup script
ibek build-startup ${PYDANTIC_DIR}/test.ibek.ioc.yaml ${PYDANTIC_DIR}/test.ibek.support.yaml --out $PYDANTIC_DIR/st.cmd --db-out $PYDANTIC_DIR/make_db.sh
