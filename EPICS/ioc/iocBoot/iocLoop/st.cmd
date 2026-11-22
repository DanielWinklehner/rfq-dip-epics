#!../../bin/linux-x86_64/mist2
## st.cmd - loop IOC (soft IOC on the computer of the high-voltage platform, next to iocHV)
##
## The same file for the emulation and for the real computer. Start it with
##     ../run-ioc.sh iocLoop <sim|real>
## It has no hardware and no port file: it reads and writes the other IOCs' PVs over Channel
## Access only, starts whether or not they run, and connects when they appear. The mode only
## shows in IOC-LOOP:mode. How to configure Channel Access when it shares the computer with
## iocHV: docs/emulation/LOOP.md.
on error break

epicsEnvSet("MIST2_DB", "$(TOP)/../Db")
epicsEnvSet("STREAM_PROTOCOL_PATH", "$(MIST2_DB)")

dbLoadDatabase("$(TOP)/dbd/mist2.dbd")
mist2_registerRecordDeviceDriver(pdbbase)

dbLoadRecords("$(MIST2_DB)/ioc_info.db", "P=IOC-LOOP")

## Loops: one line each (EPICS/Db/loop.db). Settings and their defaults: limits.defaults.

# Discharge current (REK, measured) through the filament heating current (TDK, actuator).
# Permits: interlock closed (rack IOC), REK output on in remote control, TDK output on.
# Heartbeat: the platform IOC, which owns the measurement. RES: the TDK takes the current with
# two decimals (tdk.proto, PC %.2f). SCAN .2 second: a fifth of the plant's time constant
# (about 1.4 s, model) and at most 5 writes per second on the TDK line (docs/emulation/LOOP.md).
dbLoadRecords("$(MIST2_DB)/loop.db", "P=LOOP-DIS,MEAS=REK-1:current:read,ACT=TDK:current:setpoint,HB=IOC-HV:heartbeat,C1=interlock_open,R1=0,W1=interlock open,C2=REK-1:status:read,R2=1,W2=REK not on in remote,C3=TDK:status:get,R3=1,W3=TDK output off,EGU=A,OEGU=A,OLO=0,OHI=300,RES=0.01,SCAN=.2 second")

## Settings of the loops: autosave, as the current limits on the other IOCs. At the start the
## defaults file of this IOC is restored, then the file saved at run time in
## $(MIST2_SAVE)/$(IOC), which overrides it. Every PV of a record with info(autosaveFields, ...)
## is saved within 5 s of a change. The mode is not among them: a loop starts in MANUAL.
set_savefile_path("$(MIST2_SAVE)/$(IOC)")
set_requestfile_path("$(MIST2_SAVE)/$(IOC)")
save_restoreSet_DatedBackupFiles(0)
set_pass0_restoreFile("$(TOP)/iocBoot/$(IOC)/limits.defaults")
set_pass0_restoreFile("limits.sav")
afterIocRunning("makeAutosaveFileFromDbInfo $(MIST2_SAVE)/$(IOC)/limits.req autosaveFields")
afterIocRunning("create_monitor_set limits.req 5")

iocInit
