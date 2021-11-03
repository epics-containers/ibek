cd "$(TOP)"

epicsEnvSet "EPICS_CA_MAX_ARRAY_BYTES", '6000000'
epicsEnvSet "EPICS_TS_MIN_WEST", '60'
epicsEnvSet "EPICS_CA_SERVER_PORT", '5010'

dbLoadDatabase "dbd/ioc.dbd"
ioc_registerRecordDeviceDriver(pdbbase)

pmacAsynIPConfigure(BRICK1port, 192.168.0.12:1112)
pmacCreateController(BL45P-MO-BRICK-01, BRICK1port, 0, 8, 500, 100)
pmacCreateAxes(BL45P-MO-BRICK-01, 8)

dbLoadRecords("pmacController.template", "PMAC=BL45P-MO-STEP-01:")
dbLoadRecords("pmacStatus.template", "PMAC=BL45P-MO-STEP-01:")
dbLoadRecords("$(PMAC)/db/dls_pmac_asyn_motor.template", "ADDR=1, P=BL45P-MO-THIN-01, M=:X1, PORT=BL45P-MO-BRICK-01, DESC=, MRES=0.001, VELO=1.0, PREC=3.0, EGU=mm, TWV=1, DTYP=asynMotor, DIR=0, VBAS=1.0, VMAX=$(VELO), ACCL=0.5, BDST=0.0, BVEL=0.0, BACC=0.0, DHLM=10000.0, DLLM=, HLM=0.0, LLM=0.0, HLSV=MAJOR, INIT=, SREV=1000.0, RRES=0.0, ERES=0.0, JAR=0.0, UEIP=0, RDBL=0, RLINK=, RTRY=0, DLY=0.0, OFF=0.0, RDBD=0.0, FOFF=0, ADEL=0.0, NTM=1, FEHIGH=, FEHIHI=0.0, FEHHSV=NO_ALARM, FEHSV=NO_ALARM, SCALE=1, HOMEVIS=1, HOMEVISSTR=, name=X1 motor, alh=, gda_name=none, gda_desc=$(DESC), SPORT=BRICK1port, HOME=$(P), PMAC=BL45P-MO-BRICK-01, ALLOW_HOMED_SET=#")
dbLoadRecords("$(PMAC)/db/dls_pmac_asyn_motor.template", "ADDR=2, P=BL45P-MO-THIN-01, M=:Y1, PORT=BL45P-MO-BRICK-01, DESC=, MRES=0.001, VELO=1.0, PREC=3.0, EGU=mm, TWV=1, DTYP=asynMotor, DIR=0, VBAS=1.0, VMAX=$(VELO), ACCL=0.5, BDST=0.0, BVEL=0.0, BACC=0.0, DHLM=10000.0, DLLM=, HLM=0.0, LLM=0.0, HLSV=MAJOR, INIT=, SREV=1000.0, RRES=0.0, ERES=0.0, JAR=0.0, UEIP=0, RDBL=0, RLINK=, RTRY=0, DLY=0.0, OFF=0.0, RDBD=0.0, FOFF=0, ADEL=0.0, NTM=1, FEHIGH=, FEHIHI=0.0, FEHHSV=NO_ALARM, FEHSV=NO_ALARM, SCALE=1, HOMEVIS=1, HOMEVISSTR=, name=Y1 motor, alh=, gda_name=none, gda_desc=$(DESC), SPORT=BRICK1port, HOME=$(P), PMAC=BL45P-MO-BRICK-01, ALLOW_HOMED_SET=#")

iocInit()

dbpf "BL45P-MO-THIN-01:X1.TWV", "2.5"
dbpf "BL45P-MO-THIN-01:Y1.TWV", "0.5"
