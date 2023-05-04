#!/bin/bash
msi -I${EPICS_DB_INCLUDE_PATH} -M"c=4", s=0"" "Hy8401ip.template"
msi -I${EPICS_DB_INCLUDE_PATH} -M"c=4", s=2"" "Hy8401ip.template"
