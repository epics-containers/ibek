#!/bin/bash

# A system test script for ibek
#
# This tests the same IOC as the test testioc.py/test_example_ioc
# However it launches the generated IOC in a container and uses
# caget to verify that it is working as expected.
#
# STEPS:
# 1. Launch the ioc-template container in the background with these mounts:
#    example-ibek-config -> /epics/ioc/config
#        brings in the config files for the IOC
#    this repo root -> /ibek
#        mounts the same
#    this repo root/ibek-defs -> /ctools
# 2. Install this instance of ibek into the container's global venv
#    using /ibek
# 3. Launch the IOC by running /epics/ioc/start_ioc.sh
#    (backgrounded)
# 4. Use the epics-base container to check the IOC is
#    working as expected by invoking caget and caput.
#

# NOTE: IFS= means that spaces in variable expansion are not treated as
# separators. This avoids copious quoting to protect against paths with
# spaces in them.
# This also means that we need to use ${array[@]} to expand arrays of
# arguments like base_args and ioc_args below (and that these arrays are
# declared with parentheses instead of quotes)

IFS=
THIS_DIR=$(realpath $(dirname $0))
ROOT=$(realpath ${THIS_DIR}/..)

set -ex

# make ibek-defs available
git submodule update --init --recursive

base_args=(
    --rm
    --network podman
    -e EPICS_CA_SERVER_PORT=7064
    ghcr.io/epics-containers/epics-base-linux-runtime:7.0.7ec2
)

check_pv () {
    podman run ${base_args[@]} caget ${1} > /tmp/pv_out.txt
    if ! grep -q ${2} /tmp/pv_out.txt ; then
        echo "ERROR: IOC unexpected result from ${1}:SUM"
        cat /tmp/pv_out.txt
        return 1
    fi
}

check_ioc() {
    podman run ${base_args[@]} caput ${1}:A 1.4
    podman run ${base_args[@]} caput ${1}:B 1.5
    podman run ${base_args[@]} caput ${1}:SUM.PROC 0
    check_pv ${1}:SUM 2.9
}

cont="ibek-test-container"
config="/epics/ioc/config"
ioc_args=(
    --security-opt label=disable
    --network podman
    --name ${cont}
    --entrypoint bash
    -dit
    ghcr.io/epics-containers/ioc-template-example-developer:4.0.0
)
mounts=(
    -v ${THIS_DIR}/samples/example-ibek-config:${config}
    -v ${ROOT}:/ibek
    -v ${ROOT}/ibek-defs:/ctools
)

cd ${ROOT}
rm -f start.log

# remove any existing container
if podman container exists ${cont}; then
    podman rm -ft0 ${cont}
fi
# launch epics-base container in the background
podman run  ${mounts[@]} ${ioc_args[@]}
# install the this ibek into it's global venv
podman exec ${cont} pip install /ibek
# launch the IOC
podman exec -dit ${cont} bash -c "/epics/ioc/start.sh >> /ibek/start.log 2>&1"
# wait for ibek to get the IOC up and running.
for retry in {1..10} ; do
    if check_pv 'test-ibek-ioc:EPICS_VERS' 'R7.0.8'; then break; fi
    sleep 1
done
# output the log from the IOC
cat start.log
# verify expected PVs
check_pv 'test-ibek-ioc:EPICS_VERS' 'R7.0.8'
check_ioc 'EXAMPLE:IBEK'
