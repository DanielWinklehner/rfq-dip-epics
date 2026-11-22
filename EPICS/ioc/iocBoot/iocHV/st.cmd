#!../../bin/linux-x86_64/mist2
## st.cmd - platform IOC (the control computer on the high-voltage platform)
##
## The same file for the emulation and for the real computer. Start it with
##     ../run-ioc.sh iocHV <sim|real>
## which sets TOP, IOC and MIST2_PORTS. The asyn ports come from ports.$(MIST2_PORTS).cmd.

## Any failing command stops the startup and the IOC exits with code 1 (mist2Main.cpp):
## an unset MIST2_PORTS, a missing port file or a failing dbLoadRecords never leaves a
## half-configured IOC running. The setting does not reach into files loaded with iocshLoad,
## so each port file starts with its own "on error break".
on error break

epicsEnvSet("MIST2_DB", "$(TOP)/../Db")

## Channel Access links to other IOCs (the permit interlock_open of the rack IOC): a peer that
## goes silent without closing its connection is noticed after EPICS_CA_CONN_TMO seconds and an
## echo. Our choice: 5 s instead of the default 30 s, so that a lost permit switches the REK off
## and hands a control loop back within seconds (docs/emulation/LOOP.md). Must be set before
## iocInit, which starts the links.
epicsEnvSet("EPICS_CA_CONN_TMO", "5")
epicsEnvSet("STREAM_PROTOCOL_PATH", "$(MIST2_DB)")

dbLoadDatabase("$(TOP)/dbd/mist2.dbd")
mist2_registerRecordDeviceDriver(pdbbase)

## Asyn ports: emulation (sim) or real serial ports (real)
iocshLoad("$(TOP)/iocBoot/$(IOC)/ports.$(MIST2_PORTS).cmd")

dbLoadRecords("$(MIST2_DB)/ioc_info.db", "P=IOC-HV")

## Devices
## Prefixes are those of the lab's IOC of 2023 (reference/lab-2023/EPICS/st.cmd).

# Filament heating: TDK-Lambda GENESYS 8-300 (address 6)
dbLoadRecords("$(MIST2_DB)/tdk.db",            "PORT=TDK,DEVICE=TDK,ADR=6")

# Filament discharge: Matsusada REK150-24, unit 1. For the REK150-55 add IFS=55.
# PERMIT (default interlock_open) is a PV of the rack IOC, read over Channel Access. Losing it
# switches the output off and clears the request (latch).
dbLoadRecords("$(MIST2_DB)/rek.db",            "PORT=REK,UNITNUM=1")

# Thermocouple board (libcom1)
dbLoadRecords("$(MIST2_DB)/thermocouples.db",  "PORT=thermo,DEVICE=THM")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db", "PORT=thermo,DEVICE=THM")

## Control loops: the records of each loop (EPICS/Db/loop.db). The algorithm is the Python
## service loops/mist2loop beside this IOC; these records also enforce, without it, the output
## and slew limits and that the actuator is written only in PID (docs/emulation/LOOP.md).

# Discharge current (REK, measured) through the filament heating current (TDK, actuator).
# Permits: interlock closed (rack IOC), REK output on in remote control, TDK output on. RES: the
# TDK takes the current with two decimals (tdk.proto, PC %.2f). SCAN .2 second: a seventh of the
# plant's time constant (about 1.4 s, model), at most 5 sets per second on the TDK's line.
dbLoadRecords("$(MIST2_DB)/loop.db",           "P=LOOP-DIS,MEAS=REK-1:current:read,ACT=TDK:current:setpoint,HB=IOC-HV:heartbeat,C1=interlock_open,R1=0,W1=interlock open,C2=REK-1:status:read,R2=1,W2=REK not on in remote,C3=TDK:status:get,R3=1,W3=TDK output off,EGU=A,OEGU=A,OLO=0,OHI=300,RES=0.01,SCAN=.2 second,DT=0.2")

## Limits (the current limits of the HV supplies) and the settings of the loops: autosave. At the start the defaults file of
## this IOC is restored, then the file saved at run time in $(MIST2_SAVE)/$(IOC), which
## overrides it (missing at the first start: the defaults apply). Every PV of a record with
## info(autosaveFields, ...) is saved within 5 s of a change. run-ioc.sh creates the directory.
set_savefile_path("$(MIST2_SAVE)/$(IOC)")
set_requestfile_path("$(MIST2_SAVE)/$(IOC)")
save_restoreSet_DatedBackupFiles(0)
set_pass0_restoreFile("$(TOP)/iocBoot/$(IOC)/limits.defaults")
set_pass0_restoreFile("limits.sav")
afterIocRunning("makeAutosaveFileFromDbInfo $(MIST2_SAVE)/$(IOC)/limits.req autosaveFields")
afterIocRunning("create_monitor_set limits.req 5")

iocInit
