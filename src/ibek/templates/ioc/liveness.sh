#!/bin/bash
TOP=/epics/ioc
cd ${TOP}
CONFIG_DIR=${TOP}/config

set -ex

CONFIG_DIR=/epics/ioc/config
THIS_SCRIPT=$(realpath ${0})
override=${CONFIG_DIR}/liveness.sh

if [[ -f ${override} && ${override} != ${THIS_SCRIPT} ]]; then
    exec bash ${override}
fi

if [[ ${K8S_IOC_LIVENESS_ENABLED} != 'true' ]]; then
    exit 0
fi

# use devIOCStats UPTIME as the default liveness PV
# but allow override from the environment
K8S_IOC_PV=${K8S_IOC_PV:-"${IOC_PREFIX}:UPTIME"}

# use default CA PORT or override from the environment
K8S_IOC_PORT=${K8S_IOC_PORT:-5064}

export EPICS_CA_ADDR_LIST=${K8S_IOC_ADDRESS}
export EPICS_CA_SERVER_PORT=${K8S_IOC_PORT}

# verify that the IOC is running
if caget ${K8S_IOC_PV} ; then
    exit 0
else
    # send the error message to the container's main process stdout
    echo "Liveness check failed for ${IOC_NAME}" > /proc/1/fd/1
    echo "Failing PV: ${K8S_IOC_PV}" > /proc/1/fd/2
    echo "Address list: ${EPICS_CA_ADDR_LIST}" > /proc/1/fd/2
    echo "CA Port: ${EPICS_CA_SERVER_PORT}" > /proc/1/fd/2
    exit 1
fi
