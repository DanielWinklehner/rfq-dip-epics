#!../../bin/linux-x86_64/mist2
## st.cmd - rack IOC (the control computer in the rack)
##
## The same file for the emulation and for the real computer. Start it with
##     ../run-ioc.sh iocRack <sim|real>
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

dbLoadRecords("$(MIST2_DB)/ioc_info.db", "P=IOC-RACK")

## State of the data logger (logger/), written by it over Channel Access once a second
dbLoadRecords("$(MIST2_DB)/logger_status.db", "P=LOGGER")

## Devices
## Prefixes are those of the lab's IOC of 2023 (reference/lab-2023/EPICS/st.cmd).

# High-voltage supplies Matsusada AU, four on two optical chains (owner, 2026-11-21). The PV
# name is built from the unit number. PERMIT (default interlock_open) forces an output off while
# it is non-zero or INVALID, and clears its request (latch).
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_opt,UNITNUM=1,IFS=15")  # ion source, AU20P15
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_opt,UNITNUM=2")         # puller, AU20N7.5
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_co,UNITNUM=3")          # lens 1, AU20P7.5
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_co,UNITNUM=4")          # lens 2, AU20N7.5
# One command for all outputs off: #AL SW0 on both chains
dbLoadRecords("$(MIST2_DB)/au_alloff.db", "PORT1=mat_opt,PORT2=mat_co,R1=AU-20P7-1:SetToggleOutput,R2=AU-20P7-2:SetToggleOutput,R3=AU-20P7-3:SetToggleOutput,R4=AU-20P7-4:SetToggleOutput")

# Vacuum gauges: homemade controller for APG and AIM (libcom1), and the Edwards nAIM
dbLoadRecords("$(MIST2_DB)/pressure.db",       "PORT=AVR6,DEVICE=PRESSURE")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db", "PORT=AVR6,DEVICE=PRESSURE")
dbLoadRecords("$(MIST2_DB)/aim.db",            "PORT=AIM,DEVICE=AIM")

# Sensor box: temperatures and water flows (libcom1)
dbLoadRecords("$(MIST2_DB)/sensorbox.db",      "PORT=AVR10,DEVICE=SENSOR")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db", "PORT=AVR10,DEVICE=SENSOR")

# Old interlock box: two door switches and interlock_open (libcom1)
dbLoadRecords("$(MIST2_DB)/interlockbox.db",   "PORT=AVR11,DEVICE=INTLK")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db", "PORT=AVR11,DEVICE=INTLK")

# Solenoid valve box, 8 channels (libcom1)
dbLoadRecords("$(MIST2_DB)/solenoidbox.db",    "PORT=AVR12,DEVICE=VALVE")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db", "PORT=AVR12,DEVICE=VALVE")

# Mass flow controller MKS GV50A (RS-485, address 254)
dbLoadRecords("$(MIST2_DB)/mfc.db",            "PORT=MFC,DEVICE=MFC,ADDR=254")

# Faraday cup readout (Arduino Opta, libcom1 over TCP)
dbLoadRecords("$(MIST2_DB)/faradaycup.db",     "PORT=FC,DEVICE=FC")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db", "PORT=FC,DEVICE=FC")

# Turbopumps: one Opta for both Leybold NT 20 (libcom1 over TCP), one listen-only port per pump
dbLoadRecords("$(MIST2_DB)/turbo.db",          "PORT=TURBO,DEVICE=TURBO")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db", "PORT=TURBO,DEVICE=TURBO")
dbLoadRecords("$(MIST2_DB)/turbo_pump.db",     "P=TURBO1,DEVICE=TURBO,PORT=TURBO,RELAY=r1,RUN=0,NORMAL=4,ACCEL=5,FAILURE=6")
dbLoadRecords("$(MIST2_DB)/turbo_pump.db",     "P=TURBO2,DEVICE=TURBO,PORT=TURBO,RELAY=r2,RUN=1,NORMAL=7,ACCEL=8,FAILURE=9")
dbLoadRecords("$(MIST2_DB)/nt20_monitor.db",   "P=TURBO1,PORT=NT20_1")
dbLoadRecords("$(MIST2_DB)/nt20_monitor.db",   "P=TURBO2,PORT=NT20_2")

## Limits (the current limits of the HV supplies): autosave. At the start the defaults file of
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
