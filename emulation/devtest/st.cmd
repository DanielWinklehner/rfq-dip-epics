## st.cmd of the device test harness (run.sh). The prologue is that of iocBoot/*/st.cmd,
## the case adds its ports and databases in ioc.cmd. Macros from the environment:
##   TOP (the EPICS top), CASE_DIR (the case directory), SIM_HOST (the simulator container)
on error break

epicsEnvSet("MIST2_DB", "$(TOP)/../Db")
epicsEnvSet("STREAM_PROTOCOL_PATH", "$(MIST2_DB):$(CASE_DIR)")

dbLoadDatabase("$(TOP)/dbd/mist2.dbd")
mist2_registerRecordDeviceDriver(pdbbase)

## The harness waits for DEVTEST:heartbeat before it starts the tests.
dbLoadRecords("$(MIST2_DB)/ioc_info.db", "P=DEVTEST")

## The case: asyn ports and dbLoadRecords. run.sh writes build/ioc.cmd: "on error break" and
## then the case's ioc.cmd, so that a failing line of the case stops the IOC (the setting of
## this file does not reach into a file loaded with iocshLoad).
iocshLoad("$(CASE_DIR)/build/ioc.cmd")

iocInit
