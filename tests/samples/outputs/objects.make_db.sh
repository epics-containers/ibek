#!/bin/bash
msi -I${EPICS_DB_INCLUDE_PATH} -M"name=Consumer of another port, ip=10.0.0.2, value=AsynPort2.10.0.0.2" "test.db"
msi -I${EPICS_DB_INCLUDE_PATH} -M"name=Another Consumer of the 2nd port, ip=10.0.0.2, value=AsynPort2.10.0.0.2" "test.db"
