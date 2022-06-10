#!/bin/bash

#
# generic kubernetes IOC startup script
#
this_dir=$(realpath $(dirname $0))
TOP=$(realpath ${this_dir}/..)
cd ${this_dir}

set -x -e

# add module paths to environment for use in ioc startup script
source ${SUPPORT}/configure/RELEASE.shell

# if there is a non-zero length config.tz then decompress into config_untar
if [ -s config.tz ]
then
    # decompress the configuration files into config_untar (/tmp is writeable)
    config_dir=/tmp/config_untar

    mkdir -p ${config_dir}
    tar -zxvf config.tz -C ${config_dir}
else
    config_dir=${TOP}/config
fi

# setup filenames for boot scripts
startup_src=${config_dir}/ioc.boot.yaml
boot_src=${config_dir}/ioc.boot
db_src=/tmp/make_db.sh
boot=/tmp/$(basename ${boot_src})
db=/tmp/ioc.db

# If there is a yaml ioc description then generate the startup and DB.
# Otherwise assume the starup script ioc.boot is provided in the config folder.
if [ -f ${startup_src} ] ; then
    # get ibek defs files from this ioc and all support modules and this IOC
    # defs="${SUPPORT}/*/ibek/*.ibek.defs.yaml ${TOP}/ibek/*.ibek.defs.yaml"

    # TODO - for early development we ship all latest def files in ioc/ibek
    defs=${TOP}/ibek/*.ibek.defs.yaml
    ibek build-startup ${startup_src} ${defs} --out ${boot} --db-out ${db_src}
fi

# build expanded database using the db_src shell script
if [ -f ${db_src} ]; then
    bash ${db_src} > ${db}
fi
exec ${IOC}/bin/linux-x86_64/ioc ${boot}
