cd "$(TOP)"
epicsEnvSet "EPICS_CA_MAX_ARRAY_BYTES", '6000000'
epicsEnvSet "EPICS_TS_MIN_WEST", '0'
cd "$(TOP)"
dbLoadDatabase "dbd/ioc.dbd"
ioc_registerRecordDeviceDriver(pdbbase)
pmacAsynIPConfigure(BRICK1port, 192.168.0.12:1112)
pmacCreateController(BL45P-MO-BRICK-01, BRICK1port, 0, 8, 500, 100)
pmacCreateAxes(BL45P-MO-BRICK-01, 8)



dbLoadRecords("pmacController.template", "PMAC=BL45P-MO-STEP-01:")
dbLoadRecords("pmacStatus.template", "PMAC=BL45P-MO-STEP-01:")
dbLoadRecords("$(PMAC)/db/dls_pmac_asyn_motor.template", "P=BL45P-MO-THIN-01, M=:X1, PORT=BL45P-MO-BRICK-01, ADDR=1, DESC= , MRES=0.001, VELO=1.0, PREC=, EGU=mm, TWV=1, DTYP=asynMotor, DIR=0, VBAS=1.0, VMAX=1, ACCL=0.5, BDST=0, BVEL=0, BACC=0, DHLM=10000, DLLM=, HLM=0, LLM=0, HLSV=MAJOR, INIT= , SREV=1000, RRES=0, ERES=0, JAR=0, UEIP=0, RDBL=0, RLINK=, RTRY=0, DLY=0, OFF=0, RDBD=0, FOFF=0, ADEL=0, NTM=1, FEHIGH=0, FEHIHI=0, FEHHSV=NO_ALARM, FEHSV=NO_ALARM, SCALE=1, HOMEVIS=1, HOMEVISSTR=, name=X1 motor, alh= , gda_name=none, gda_desc=$(DESC), SPORT=BRICK1port, HOME=$(P), PMAC=BL45P-MO-BRICK-01, ALLOW_HOMED_SET=#")
dbLoadRecords("$(PMAC)/db/dls_pmac_asyn_motor.template", "P=BL45P-MO-THIN-01, M=:Y1, PORT=BL45P-MO-BRICK-01, ADDR=2, DESC= , MRES=0.001, VELO=1.0, PREC=, EGU=mm, TWV=1, DTYP=asynMotor, DIR=0, VBAS=1.0, VMAX=1, ACCL=0.5, BDST=0, BVEL=0, BACC=0, DHLM=10000, DLLM=, HLM=0, LLM=0, HLSV=MAJOR, INIT= , SREV=1000, RRES=0, ERES=0, JAR=0, UEIP=0, RDBL=0, RLINK=, RTRY=0, DLY=0, OFF=0, RDBD=0, FOFF=0, ADEL=0, NTM=1, FEHIGH=0, FEHIHI=0, FEHHSV=NO_ALARM, FEHSV=NO_ALARM, SCALE=1, HOMEVIS=1, HOMEVISSTR=, name=Y1 motor, alh= , gda_name=none, gda_desc=$(DESC), SPORT=BRICK1port, HOME=$(P), PMAC=BL45P-MO-BRICK-01, ALLOW_HOMED_SET=#")

cd "$(TOP)"
iocInit()

