cd "/repos/epics/ioc"

dbLoadDatabase "dbd/ioc.dbd"
ioc_registerRecordDeviceDriver(pdbbase)


dbLoadRecords("/tmp/ioc.db")
iocInit()

dbpf "BL45P-MO-THIN-01:Y1.TWV", "0.5"
