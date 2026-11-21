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

## Devices
## Prefixes are those of the lab's IOC of 2023 (reference/lab-2023/EPICS/st.cmd).

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

iocInit
