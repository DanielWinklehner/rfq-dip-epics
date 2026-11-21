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

# Thermocouple board (libcom1)
dbLoadRecords("$(MIST2_DB)/thermocouples.db",  "PORT=thermo,DEVICE=THM")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db", "PORT=thermo,DEVICE=THM")

iocInit
