# EPICS IOC Startup Script generated by https://github.com/epics-containers/ibek

cd "/epics/ioc"

epicsEnvSet NAME_AS_ENV_VAR my name is controllerPort1
epicsEnvSet NAME_AS_ENV_VAR my name is controllerPort2
epicsEnvSet NAME_AS_ENV_VAR my name is controllerPort3

dbLoadDatabase dbd/ioc.dbd
ioc_registerRecordDeviceDriver pdbbase

hello world from a
hello world from b
hello world from c
hello world from 1
hello world from 2
hello world from 3
NESTED 1a
NESTED 1b
NESTED 1c
NESTED 2a
NESTED 2b
NESTED 2c
NESTED 3a
NESTED 3b
NESTED 3c
# Setting up Asyn Port controllerPort1 on 192.168.0.55:2003:
# AsynIPConfigure({{name}}, {{port}}, {{stop}}, {{parity}}, {{bits}}) 
AsynIPConfigure(controllerPort1, 192.168.0.55:2003, 1, none, 8)
asynSetOption(9600, 0, N, Y)
asynOctetSetInputEos("\n")
asynOctetSetOutputEos("\n")
# Setting up Asyn Port controllerPort2 on 192.168.0.55:2004:
AsynIPConfigure(controllerPort2, 192.168.0.55:2004, 1, none, 8)
asynSetOption(9600, 0, N, Y)
asynOctetSetInputEos("\n")
asynOctetSetOutputEos("\n")
# Setting up Asyn Port controllerPort3 on 192.168.0.55:2005:
AsynIPConfigure(controllerPort3, 192.168.0.55:2005, 1, none, 8)
asynSetOption(9600, 0, N, Y)
asynOctetSetInputEos("\n")
asynOctetSetOutputEos("\n")
# motorSimCreateController(controller_asyn_port_name, axis_count)
# testing escaping:  {{enclosed in escaped curly braces}} 
motorSimCreateController(controller1, 4)
# motorSimCreateController(controller_asyn_port_name, axis_count)
# testing escaping:  {{enclosed in escaped curly braces}} 
motorSimCreateController(controller2, 4)
# motorSimCreateController(controller_asyn_port_name, axis_count)
# testing escaping:  {{enclosed in escaped curly braces}} 
motorSimCreateController(controller3, 4)

dbLoadRecords /epics/runtime/ioc.db
iocInit
