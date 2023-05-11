# EPICS IOC Startup Script generated by https://github.com/epics-containers/ibek

cd "/repos/epics/ioc"

epicsEnvSet Vec0 192

dbLoadDatabase dbd/ioc.dbd
ioc_registerRecordDeviceDriver pdbbase


# ipacAddHy8002 "slot, interrupt_level"
#   Create a new Hy8002 carrier.
#   The resulting carrier handle (card id) is saved in an env variable.
ipacAddHy8002 "4, 2"
epicsEnvSet IPAC4 0 0 0
ipacAddHy8002 "5, 2"
epicsEnvSet IPAC5 1 1 1

dbLoadRecords /tmp/ioc.db
iocInit

