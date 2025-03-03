#!/bin/bash

# this script regenerates the files used in tests
# it is useful after making changes to the code that affect the schemas etc.
#
# please bear in mind that this is cheating tests! It requires visual
# verifiction of the files in the samples folders after running.
#

export SAMPLES_DIR=$(realpath $(dirname "${BASH_SOURCE[0]}"))/samples

export EPICS_ROOT=${SAMPLES_DIR}/epics
export IOC="/epics/ioc"
export RUNTIME_DIR="/epics/runtime"
export IOC_NAME=TEST_IOC

# this is so relative schema mode lines work
cd $SAMPLES_DIR
mkdir -p schemas
mkdir -p outputs

set -e

mkdir -p epics/pvi-defs
cp support/simple.pvi.device.yaml  epics/pvi-defs/simple.pvi.device.yaml

# general schema for all support yaml ######################################

echo making the support yaml schema
ibek support generate-schema --output schemas/ibek.support.schema.json


############################################################################
# repeat tests IOCs
############################################################################

echo making repeat ioc
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/repeat.ibek.ioc.yaml support/asyn.ibek.support.yaml support/epics.ibek.support.yaml support/motorSim.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/repeat

echo making subentity repeat ioc
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/subentity_test.ibek.ioc.yaml support/subentity_test.ibek.support.yaml support/epics.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/subentity_test


############################################################################
# quadem example
############################################################################

echo making an ioc schema using ADCore and quadem support yaml
ibek ioc generate-schema --no-ibek-defs support/ADCore.ibek.support.yaml support/quadem.ibek.support.yaml --output schemas/quadem.ibek.ioc.schema.json

echo making ioc based on quadem support yaml
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/quadem.ibek.ioc.yaml support/ADCore.ibek.support.yaml support/quadem.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/quadem

echo making an ioc schema using ADCore and quadem repeat support yaml
ibek ioc generate-schema --no-ibek-defs support/ADCore.ibek.support.yaml support/quadem_repeat.ibek.support.yaml --output schemas/quadem_repeat.ibek.ioc.schema.json

echo making ioc based on quadem_repeat support yaml
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/quadem.ibek.ioc.yaml support/ADCore.ibek.support.yaml support/quadem_repeat.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/quadem_repeat


############################################################################
# motorSim example
############################################################################

echo making an ioc schema using just motorSim support yaml
ibek ioc generate-schema --no-ibek-defs support/motorSim.ibek.support.yaml --output schemas/single.ibek.ioc.schema.json

echo making an ioc schema using motorSim and Asyn support yaml
ibek ioc generate-schema --no-ibek-defs support/asyn.ibek.support.yaml support/motorSim.ibek.support.yaml --output schemas/motorSim.ibek.ioc.schema.json

echo making ioc based on ibek-mo-ioc-01.yaml
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/motorSim.ibek.ioc.yaml support/asyn.ibek.support.yaml support/motorSim.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/motorSim


############################################################################
# utils example
############################################################################

echo making an ioc schema using utils support yaml
ibek ioc generate-schema --no-ibek-defs support/utils.ibek.support.yaml --output schemas/utils.ibek.ioc.schema.json

echo making ioc based on utils support yaml
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/utils.ibek.ioc.yaml support/utils.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/utils


############################################################################
# ipac example
############################################################################

echo making an ioc schema using utils support yaml
ibek ioc generate-schema --no-ibek-defs support/ipac.ibek.support.yaml support/epics.ibek.support.yaml --output schemas/ipac.ibek.ioc.schema.json

echo making ioc based on ipac support yaml
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/ipac-test.ibek.ioc.yaml support/ipac.ibek.support.yaml support/epics.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/ipac-test


############################################################################
# gauges example
############################################################################

echo making an ioc schema using asyn and gauges support yaml
ibek ioc generate-schema --no-ibek-defs support/asyn.ibek.support.yaml support/gauges.ibek.support.yaml --output schemas/gauges.ibek.ioc.schema.json

echo making ioc based on gauges support yaml
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/gauges.ibek.ioc.yaml support/asyn.ibek.support.yaml support/gauges.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/gauges


############################################################################
# technosoft motor example
############################################################################

echo making an ioc schema using technosoft support yaml
ibek ioc generate-schema --no-ibek-defs support/technosoft.ibek.support.yaml --output schemas/technosoft.ibek.ioc.schema.json

echo making techosoft ioc
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/technosoft.ibek.ioc.yaml support/technosoft.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/technosoft


############################################################################
# list example
############################################################################

echo making an ioc schema using listarg support yaml
ibek ioc generate-schema --no-ibek-defs support/listarg.ibek.support.yaml --output schemas/listarg.ibek.schema.json

echo making listarg ioc
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/listarg.ibek.ioc.yaml support/listarg.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/listarg



############################################################################
# fast vacuum (dlsPLC) example
############################################################################

echo making an ioc schema using fastVacuum support yaml
ibek ioc generate-schema --no-ibek-defs support/fastVacuum.ibek.support.yaml --output schemas/fastVacuum.ibek.ioc.schema.json

echo making fastVacuum ioc
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/fastVacuum.ibek.ioc.yaml support/fastVacuum.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/fastVacuum



############################################################################
# vacValveDebounce (dlsPLC) example
############################################################################

echo making an ioc schema using dlsPLC support yaml
ibek ioc generate-schema --no-ibek-defs support/dlsPLC.ibek.support.yaml support/asyn.ibek.support.yaml --output schemas/dlsPLC.ibek.ioc.schema.json

echo making fastVacuum ioc
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/dlsPLC.ibek.ioc.yaml support/dlsPLC.ibek.support.yaml support/asyn.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/dlsPLC
