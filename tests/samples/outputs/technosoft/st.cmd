# EPICS IOC Startup Script generated by https://github.com/epics-containers/ibek

cd "/epics/ioc"
dbLoadDatabase dbd/ioc.dbd
ioc_registerRecordDeviceDriver pdbbase

ndsCreateDevice "TechnosoftTML", "TML", "FILE=/tmp/,NAXIS=2,DEV_PATH=/tmp,HOST_ID=15,AXIS_SETUP_0=$(SUPPORT)/motorTechnosoft/tml_lib/config/star_vat_phs.t.zip,AXIS_ID_0=15,AXIS_HOMING_SW_0=LSN,AXIS_SETUP_1=$(SUPPORT)/motorTechnosoft/tml_lib/config/star_vat_phs.t.zip,AXIS_ID_1=17,AXIS_HOMING_SW_1=LSN"
dbLoadRecords("$(SUPPORT)/motorTechnosoft/db/tmlAxis.template","PREFIX=SPARC:TML, CHANNEL_ID=MOT, CHANNEL_PREFIX=ax0, ASYN_PORT=TML, ASYN_ADDR=0, NSTEPS=200, NMICROSTEPS=256, VELO=20, VELO_MIN=0.1, VELO_MAX=50.0, ACCL=0.5, ACCL_MIN=0.01, ACCL_MAX=1.5, HAR=0.5, HVEL=10.0, JAR=1, JVEL=5, ENABLED=1, SLSP=0.8, EGU=ustep, TIMEOUT=0")
dbLoadRecords("$(SUPPORT)/motorTechnosoft/db/tmlAxis.template","PREFIX=SPARC:TML, CHANNEL_ID=MOT, CHANNEL_PREFIX=ax1, ASYN_PORT=TML, ASYN_ADDR=0, NSTEPS=200, NMICROSTEPS=256, VELO=20, VELO_MIN=0.1, VELO_MAX=50.0, ACCL=0.5, ACCL_MIN=0.011, ACCL_MAX=1.5, HAR=0.5, HVEL=10.0, JAR=1, JVEL=5, ENABLED=1, SLSP=0.8, EGU=SPARC:TML, TIMEOUT=0")

dbLoadRecords /epics/runtime/ioc.db
iocInit



dbpf("SPARC:TML:MOT:MSGRS","START")
dbl

dbpf("SPARC:TML:MOT:MSGRS","START")
dbl
