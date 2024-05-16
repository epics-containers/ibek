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

# this is so relative schema mode lines work
cd $SAMPLES_DIR
mkdir -p schemas
mkdir -p outputs

set -ex

mkdir -p epics/pvi-defs
cp support/simple.pvi.device.yaml  epics/pvi-defs/simple.pvi.device.yaml

echo making the support yaml schema
ibek support generate-schema --output schemas/ibek.support.schema.json

echo making an ioc schema using just motorSim support yaml
ibek ioc generate-schema --no-ibek-defs support/motorSim.ibek.support.yaml --output schemas/single.ibek.ioc.schema.json

echo making an ioc schema using motorSim and Asyn support yaml
ibek ioc generate-schema --no-ibek-defs support/asyn.ibek.support.yaml support/motorSim.ibek.support.yaml --output schemas/motorSim.ibek.ioc.schema.json

echo making an ioc schema using utils support yaml
ibek ioc generate-schema --no-ibek-defs support/utils.ibek.support.yaml --output schemas/utils.ibek.ioc.schema.json

echo making an ioc schema using asyn and gauges support yaml
ibek ioc generate-schema --no-ibek-defs support/asyn.ibek.support.yaml support/gauges.ibek.support.yaml --output schemas/gauges.ibek.ioc.schema.json

echo making an ioc schema using ADCore and quadem support yaml
ibek ioc generate-schema --no-ibek-defs support/ADCore.ibek.support.yaml support/quadem.ibek.support.yaml --output schemas/quadem.ibek.ioc.schema.json

echo making ioc based on ibek-mo-ioc-01.yaml
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/ibek-mo-ioc-01.yaml support/asyn.ibek.support.yaml support/motorSim.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/motorSim

echo making ioc based on utils support yaml
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/utils.ibek.ioc.yaml support/utils.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/utils

echo making ioc based on ipac support yaml
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/ipac-test.yaml support/ipac.ibek.support.yaml support/epics.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/ipac

echo making ioc based on gauges support yaml
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/gauges.ibek.ioc.yaml support/asyn.ibek.support.yaml support/gauges.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/gauges

echo making ioc based on quadem support yaml
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/quadem.ibek.ioc.yaml support/ADCore.ibek.support.yaml support/quadem.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/quadem


############################################################################

# technosoft motor example

echo making an ioc schema using technosoft support yaml
ibek ioc generate-schema --no-ibek-defs support/technosoft.ibek.support.yaml --output schemas/technosoft.ibek.ioc.schema.json

echo making techosoft ioc
EPICS_ROOT=`pwd`/epics ibek runtime generate iocs/technosoft.ibek.ioc.yaml support/technosoft.ibek.support.yaml
mv `pwd`/epics/{runtime,opi}/* `pwd`/outputs/technosoft
