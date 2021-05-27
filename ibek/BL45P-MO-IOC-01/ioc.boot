cd "$(TOP)"
epicsEnvSet "EPICS_CA_MAX_ARRAY_BYTES", '6000000'
epicsEnvSet "EPICS_TS_MIN_WEST", '0'
cd "$(TOP)"
dbLoadDatabase "dbd/ioc.dbd"
ioc_registerRecordDeviceDriver(pdbbase)
pmacAsynIPConfigure(BRICK1port, 192.168.0.12:1112)
pmacAsynIPConfigure(BRICK2port, 192.168.0.12:1112)
pmacAsynIPConfigure(BRICK3port, 192.168.0.12:1113)
pmacAsynIPConfigure(BRICK4port, 192.168.0.12:1114)
pmacAsynIPConfigure(BRICK5port, 192.168.0.12:1025)
pmacAsynIPConfigure(BRICK6port, 192.168.0.13:1025)
pmacCreateController(BL45P-MO-BRICK-01, BRICK1port, 0, 8, 500, 100)
pmacCreateAxes(BL45P-MO-BRICK-01, 8)

dbLoadRecords("pmacController.template", "PMAC = BL45P-MO-STEP-01:")
dbLoadRecords("pmacStatus.template", "PMAC = BL45P-MO-STEP-01:")
dbLoadRecords("pmac_asyn_Motor.template", "PMAC=BL45P-MO-MIRR-01:X1")

cd "$(TOP)"
iocInit