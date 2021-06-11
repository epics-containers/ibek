#!/bin/bash

#
# generic kubernetes IOC startup script
#
source ${SUPPORT}/configure/RELEASE.shell

this_dir=$(realpath $(dirname $0))
TOP=$(realpath ${this_dir}/..)

cd ${this_dir}
if [ -f config.tz ]
then
    # decompress the configuration files into config_untar
    config_dir=${TOP}/config_untar

    mkdir -p ${config_dir}
    tar -zxvf config.tz -C ${config_dir}
else
    config_dir=${TOP}/config
fi

boot=${config_dir}/ioc.boot

# Update the boot script to work in the directory it resides in
# using msi MACRO substitution.
# Output to /tmp for guarenteed writability
msi -MTOP=${TOP},THIS_DIR=${config_dir} ${boot} > /tmp/ioc.boot

exec ${EPICS_ROOT}/ioc/bin/linux-x86_64/ioc /tmp/ioc.boot