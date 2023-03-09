# A system test script for ibek
#
# STEPS:
# 1. Launch the ioc-template container in the background with these mounts:
#    example-ibek-config -> /repos/epics/ioc/config
#    this repo root -> /repos/ibek
# 2. Install this instance of ibek into the container's global venv
#    using /repos/ibek
# 3. Launch the IOC by running /repos/epics/ioc/start_ioc.sh
#    (backgrounded)
# 4. Use the epics-base container to check the IOC is
#    working as expected by invoking caget and caput.
#

THIS_DIR=$(realpath $(dirname $0))
ROOT=$(realpath ${THIS_DIR}/..)

set -ex

base_args="
    --rm
    --network podman
    -e EPICS_CA_SERVER_PORT=7064
    ghcr.io/epics-containers/epics-base-linux-runtime:23.3.1
"

check_pv () {
    podman run ${base_args} caget ${1} > /tmp/pv_out.txt
    if ! grep -q ${2} /tmp/pv_out.txt ; then
        echo "ERROR: IOC unexpected result from ${1}:SUM"
        cat /tmp/pv_out.txt
        return 1
    fi
}

check_ioc() {
    podman run ${base_args} caput ${1}:A 1.4
    podman run ${base_args} caput ${1}:B 1.5
    podman run ${base_args} caput ${1}:SUM.PROC 0
    check_pv ${1}:SUM 2.9
}

cont="ibek-test-container"
config="/repos/epics/ioc/config"
ioc_args="
--security-opt label=disable
--network podman
--name ${cont}
--entrypoint bash
-dit
ghcr.io/epics-containers/ioc-template-linux-developer:23.3.1
"
mounts="
-v ${THIS_DIR}/samples/example-ibek-config:${config}
-v ${ROOT}:/repos/ibek
"

cd ${ROOT}

# remove any existing container
if podman container exists ${cont}; then
    podman rm -ft0 ${cont}
fi
# launch epics-base container in the background
podman run  ${mounts} ${ioc_args}
# install the this ibek into it's global venv
podman exec ${cont} pip install /repos/ibek
# launch the IOC
podman exec -dit ${cont} bash -c "/repos/epics/ioc/start.sh >> /repos/ibek/start.log 2>&1"
# wait for ibek to get the IOC up and running.
for retry in {1..10} ; do
    if check_pv 'test-ibek-ioc:EPICS_VERS' 'R7.0.7'; then break; fi
    sleep 1
done
# output the log from the IOC
cat start.log
# verify expected PVs
check_pv 'test-ibek-ioc:EPICS_VERS' 'R7.0.7'
check_ioc "EXAMPLE:IBEK"


