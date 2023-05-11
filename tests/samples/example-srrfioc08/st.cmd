# EPICS IOC Startup Script generated by https://github.com/epics-containers/ibek

cd "/repos/epics/ioc"

epicsEnvSet EPICS_TS_NTP_INET 172.23.194.5
epicsEnvSet EPICS_TS_MIN_WEST 0
epicsEnvSet Vec0 192
epicsEnvSet Vec1 193
epicsEnvSet Vec2 194

dbLoadDatabase dbd/ioc.dbd
ioc_registerRecordDeviceDriver pdbbase

# ipacAddHy8002 "slot, interrupt_level"
#   Create a new Hy8002 carrier.
#   The resulting carrier handle (card id) is saved in an env variable.
ipacAddHy8002 "4, 2"
epicsEnvSet IPAC4 0
ipacAddHy8002 "5, 2"
epicsEnvSet IPAC5 1
# Hy8401ipConfigure CardId IPACid IpSiteNumber InterruptVector InterruptEnable AiType ExternalClock ClockRate Inhibit SampleCount SampleSpacing SampleSize
#   IpSlot 0=A 1=B 2=C 3=D
#   ClockRate  0=1Hz  1=2Hz  2=5Hz  3=10Hz 4=20Hz 5=50Hz 6=100Hz7=200Hz 8=500Hz 9=1kHz 10=2kHz11=5kHz 12=10kHz 13=20kHz 14=50kHz 15=100kHz
Hy8401ipConfigure 40 $(IPAC4) 0 $(Vec0) 0 0 0 15 0 1 1 0
Hy8401ipConfigure 42 $(IPAC4) 2 $(Vec1) 0 0 0 15 0 1 1 0
Hy8401ipConfigure 50 $(IPAC5) 0 $(Vec2) 0 0 0 15 0 1 1 0

dbLoadRecords /tmp/ioc.db
iocInit

