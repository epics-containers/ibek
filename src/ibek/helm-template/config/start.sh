#!/bin/bash

#
# generic kubernetes IOC startup script
#
this_dir=$(realpath $(dirname $0))
TOP=$(realpath ${this_dir}/..)
cd ${this_dir}

# add module paths to environment for use in ioc startup script
source ${SUPPORT}/configure/RELEASE.shell

# if there is a non-zero length config.tz then decompress into config_untar
if [ -s config.tz ]
then
    # decompress the configuration files into config_untar (/tmp is always writeable)
    config_dir=/tmp/config_untar

    mkdir -p ${config_dir}
    tar -zxvf config.tz -C ${config_dir}
else
    config_dir=${TOP}/config
fi

boot=${config_dir}/ioc.boot

# Update the boot script to work in the directory it resides in
# using msi MACRO substitution.
# Output to /tmp for guarenteed writability
msi -MTOP=${TOP},THIS_DIR=${config_dir},ADCORE=${adcore} ${boot} > /tmp/ioc.boot

if [ -f make_db.sh ]; then
    bash ./make_db.sh > /tmp/ioc.db
fi
exec ${IOC}/bin/linux-x86_64/ioc /tmp/ioc.boot
