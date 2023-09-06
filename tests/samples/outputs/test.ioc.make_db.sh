#!/bin/bash
msi -I${EPICS_DB_INCLUDE_PATH} -M"IOC=test-ibek-ioc" "iocAdminSoft.db"
