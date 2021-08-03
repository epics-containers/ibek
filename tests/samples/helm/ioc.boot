cd "$(TOP)"
epicsEnvSet "EPICS_CA_MAX_ARRAY_BYTES", '6000000'
epicsEnvSet "EPICS_TS_MIN_WEST", '0'
cd "$(TOP)"
dbLoadDatabase "dbd/ioc.dbd"
ioc_registerRecordDeviceDriver(pdbbase)pmacAsynIPConfigure(BRICK1port, 192.168.0.12:1112)
pmacCreateController(BL45P-MO-BRICK-01, BRICK1port, 0, 8, 500, 100)
pmacCreateAxes(BL45P-MO-BRICK-01, 8)


dbLoadRecords("pmacController.template", "PMAC=BL45P-MO-STEP-01:")
dbLoadRecords("pmacStatus.template", "PMAC=BL45P-MO-STEP-01:")
dbLoadRecords("$(PMAC)/db/dls_pmac_asyn_motor.template", "P=BL45P-MO-THIN-01, M=:X1, PORT=BL45P-MO-BRICK-01, ADDR=0, DESC= , MRES=0.001, VELO=1.0f, PREC=, EGU=mm, TWV=1, DTYP=asynMotor, DIR=0, VBAS=1.0f, VMAX=1f, ACCL=0.5f, BDST=0f, BVEL=0f, BACC=0f, DHLM=10000f, DLLM=, HLM=0f, LLM=0f, HLSV=MAJOR, INIT= , SREV=1000f, RRES=0f, ERES=0f, JAR=0f, UEIP=0, RDBL=0, RLINK=, RTRY=0, DLY=0f, OFF=0f, RDBD=0f, FOFF=0, ADEL=0f, NTM=1, FEHIGH=0f, FEHIHI=0f, FEHHSV=NO_ALARM, FEHSV=NO_ALARM, SCALE=1, HOMEVIS=1, HOMEVISSTR=, name=X1 motor, alh= , gda_name=none, gda_desc=$(DESC), SPORT=BRICK1port, HOME=$(P), PMAC=BL45P-MO-BRICK-01, ALLOW_HOMED_SET=#
")

cd "$(TOP)"
iocInit()

