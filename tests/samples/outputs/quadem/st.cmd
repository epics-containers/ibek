# EPICS IOC Startup Script generated by https://github.com/epics-containers/ibek

cd "/epics/ioc"
dbLoadDatabase dbd/ioc.dbd
ioc_registerRecordDeviceDriver pdbbase

drvAsynIPPortConfigure(XBPM1.DRVip, 172.23.103.85:10001, 100, 0, 0)
asynOctetSetInputEos(XBPM1.DRVip, 0, "\r\n")
asynOctetSetOutputEos(XBPM1.DRVip, 0, "\r")

# drvTetrAMMConfigure(portName, IPportName, RingSize)
drvTetrAMMConfigure("XBPM1.DRV", "XBPM1.DRVip", 10000)

################################################################################
# Just demonstrating that Entities can have their own pre_init AND SubEntities.
# This is the pre_init for quadem.Plugins device with id XBPM1
################################################################################

#
# ADCore path for manual NDTimeSeries.template to find base plugin template
epicsEnvSet "EPICS_DB_INCLUDE_PATH", "$(ADCORE)/db"

# NDStatsConfigure(portName, queueSize, blockingCallbacks, NDArrayPort, NDArrayAddr, maxBuffers, maxMemory, priority, stackSize, maxThreads)
# NDTimeSeriesConfigure(portName, queueSize, blockingCallbacks, NDArrayPort, NDArrayAddr, maxSignals)
NDStatsConfigure("XBPM1.STATS.I1", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDTimeSeriesConfigure("XBPM1.STATS.I1_TS", 2, 0, "XBPM1.STATS.I1", 1, 23)
dbLoadRecords("$(ADCORE)/db/NDTimeSeries.template",  "P=BL03I-EA-XBPM-01,R=Cur1, PORT=XBPM1.STATS.I1 ,ADDR=0,TIMEOUT=1,NDARRAY_PORT=XBPM1.DRV,NDARRAY_ADDR=0,NCHANS=1000,ENABLED=1")
NDStatsConfigure("XBPM1.STATS.I2", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDTimeSeriesConfigure("XBPM1.STATS.I2_TS", 2, 0, "XBPM1.STATS.I2", 1, 23)
dbLoadRecords("$(ADCORE)/db/NDTimeSeries.template",  "P=BL03I-EA-XBPM-01,R=Cur2, PORT=XBPM1.STATS.I2 ,ADDR=0,TIMEOUT=1,NDARRAY_PORT=XBPM1.DRV,NDARRAY_ADDR=0,NCHANS=1000,ENABLED=1")
NDStatsConfigure("XBPM1.STATS.I3", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDTimeSeriesConfigure("XBPM1.STATS.I3_TS", 2, 0, "XBPM1.STATS.I3", 1, 23)
dbLoadRecords("$(ADCORE)/db/NDTimeSeries.template",  "P=BL03I-EA-XBPM-01,R=Cur3, PORT=XBPM1.STATS.I3 ,ADDR=0,TIMEOUT=1,NDARRAY_PORT=XBPM1.DRV,NDARRAY_ADDR=0,NCHANS=1000,ENABLED=1")
NDStatsConfigure("XBPM1.STATS.I4", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDTimeSeriesConfigure("XBPM1.STATS.I4_TS", 2, 0, "XBPM1.STATS.I4", 1, 23)
dbLoadRecords("$(ADCORE)/db/NDTimeSeries.template",  "P=BL03I-EA-XBPM-01,R=Cur4, PORT=XBPM1.STATS.I4 ,ADDR=0,TIMEOUT=1,NDARRAY_PORT=XBPM1.DRV,NDARRAY_ADDR=0,NCHANS=1000,ENABLED=1")
NDStatsConfigure("XBPM1.STATS.SumX", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDTimeSeriesConfigure("XBPM1.STATS.SumX_TS", 2, 0, "XBPM1.STATS.SumX", 1, 23)
dbLoadRecords("$(ADCORE)/db/NDTimeSeries.template",  "P=BL03I-EA-XBPM-01,R=SumX, PORT=XBPM1.STATS.SumX ,ADDR=0,TIMEOUT=1,NDARRAY_PORT=XBPM1.DRV,NDARRAY_ADDR=0,NCHANS=1000,ENABLED=1")
NDStatsConfigure("XBPM1.STATS.SumY", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDTimeSeriesConfigure("XBPM1.STATS.SumY_TS", 2, 0, "XBPM1.STATS.SumY", 1, 23)
dbLoadRecords("$(ADCORE)/db/NDTimeSeries.template",  "P=BL03I-EA-XBPM-01,R=SumY, PORT=XBPM1.STATS.SumY ,ADDR=0,TIMEOUT=1,NDARRAY_PORT=XBPM1.DRV,NDARRAY_ADDR=0,NCHANS=1000,ENABLED=1")
NDStatsConfigure("XBPM1.STATS.SumAll", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDTimeSeriesConfigure("XBPM1.STATS.SumAll_TS", 2, 0, "XBPM1.STATS.SumAll", 1, 23)
dbLoadRecords("$(ADCORE)/db/NDTimeSeries.template",  "P=BL03I-EA-XBPM-01,R=SumAll, PORT=XBPM1.STATS.SumAll ,ADDR=0,TIMEOUT=1,NDARRAY_PORT=XBPM1.DRV,NDARRAY_ADDR=0,NCHANS=1000,ENABLED=1")
NDStatsConfigure("XBPM1.STATS.DiffX", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDTimeSeriesConfigure("XBPM1.STATS.DiffX_TS", 2, 0, "XBPM1.STATS.DiffX", 1, 23)
dbLoadRecords("$(ADCORE)/db/NDTimeSeries.template",  "P=BL03I-EA-XBPM-01,R=DiffX, PORT=XBPM1.STATS.DiffX ,ADDR=0,TIMEOUT=1,NDARRAY_PORT=XBPM1.DRV,NDARRAY_ADDR=0,NCHANS=1000,ENABLED=1")
NDStatsConfigure("XBPM1.STATS.DiffY", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDTimeSeriesConfigure("XBPM1.STATS.DiffY_TS", 2, 0, "XBPM1.STATS.DiffY", 1, 23)
dbLoadRecords("$(ADCORE)/db/NDTimeSeries.template",  "P=BL03I-EA-XBPM-01,R=DiffY, PORT=XBPM1.STATS.DiffY ,ADDR=0,TIMEOUT=1,NDARRAY_PORT=XBPM1.DRV,NDARRAY_ADDR=0,NCHANS=1000,ENABLED=1")
NDStatsConfigure("XBPM1.STATS.PosX", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDTimeSeriesConfigure("XBPM1.STATS.PosX_TS", 2, 0, "XBPM1.STATS.PosX", 1, 23)
dbLoadRecords("$(ADCORE)/db/NDTimeSeries.template",  "P=BL03I-EA-XBPM-01,R=PosX, PORT=XBPM1.STATS.PosX ,ADDR=0,TIMEOUT=1,NDARRAY_PORT=XBPM1.DRV,NDARRAY_ADDR=0,NCHANS=1000,ENABLED=1")
NDStatsConfigure("XBPM1.STATS.PosY", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDTimeSeriesConfigure("XBPM1.STATS.PosY_TS", 2, 0, "XBPM1.STATS.PosY", 1, 23)
dbLoadRecords("$(ADCORE)/db/NDTimeSeries.template",  "P=BL03I-EA-XBPM-01,R=PosY, PORT=XBPM1.STATS.PosY ,ADDR=0,TIMEOUT=1,NDARRAY_PORT=XBPM1.DRV,NDARRAY_ADDR=0,NCHANS=1000,ENABLED=1")
# NDStdArraysConfigure(portName, queueSize, blockingCallbacks, NDArrayPort, NDArrayAddr, maxBuffers, maxMemory, priority, stackSize, maxThreads)
NDStdArraysConfigure("XBPM1.ARRAYS.Arr1", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDStdArraysConfigure("XBPM1.ARRAYS.Arr2", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDStdArraysConfigure("XBPM1.ARRAYS.Arr3", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDStdArraysConfigure("XBPM1.ARRAYS.Arr4", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDStdArraysConfigure("XBPM1.ARRAYS.SumX", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDStdArraysConfigure("XBPM1.ARRAYS.SumY", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDStdArraysConfigure("XBPM1.ARRAYS.SumAll", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDStdArraysConfigure("XBPM1.ARRAYS.DiffX", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDStdArraysConfigure("XBPM1.ARRAYS.DiffY", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDStdArraysConfigure("XBPM1.ARRAYS.PosX", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)
NDStdArraysConfigure("XBPM1.ARRAYS.PosY", 2, 0, "XBPM1.DRV", 0, 0, 0, 0, 0, 1)

dbLoadRecords /epics/runtime/ioc.db
iocInit


# Increase precision of sample time for TetrAMM
dbpf("BL03I-EA-XBPM-01:DRV:SampleTime_RBV.PREC", "5")

