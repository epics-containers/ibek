# EPICS IOC Startup Script generated by https://github.com/epics-containers/ibek

cd "/epics/ioc"
dbLoadDatabase dbd/ioc.dbd
ioc_registerRecordDeviceDriver pdbbase


dbLoadRecords /epics/runtime/ioc.db
iocInit
