cd "/repos/epics/ioc"

dbLoadDatabase "dbd/ioc.dbd"
ioc_registerRecordDeviceDriver(pdbbase)

pmacAsynIPConfigure(BRICK1port, 192.168.0.12:1112)
pmacCreateController(BL45P-MO-BRICK-01, BRICK1port, 0, 8, 500, 100)
pmacCreateAxes(BL45P-MO-BRICK-01, 8)
TODO provide Jinja to generate Startup Entries
note this is interesting because builder.py has a few if clauses
for generating the necessary script

dbLoadRecords("/tmp/ioc.db")
iocInit()
