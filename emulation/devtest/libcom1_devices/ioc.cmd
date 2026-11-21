# ioc.cmd of the case libcom1_devices: the five libcom1 Arduino boards on one IOC, each on
# its own simulator (sim.yaml). Port names and DEVICE prefixes are those of the lab's st.cmd
# of 2023; in the real IOCs the ports come from ports.<sim|real>.cmd.
# The thermocouple board belongs to the platform IOC (iocHV), the other four to iocRack.

# AVR6 gauge controller, AVR10 sensor box, AVR11 interlock box, AVR12 solenoid valve box,
# thermo thermocouple board (iocsh takes no comment after a command)
drvAsynIPPortConfigure("AVR6",   "$(SIM_HOST):5006")
drvAsynIPPortConfigure("AVR10",  "$(SIM_HOST):5010")
drvAsynIPPortConfigure("AVR11",  "$(SIM_HOST):5011")
drvAsynIPPortConfigure("AVR12",  "$(SIM_HOST):5012")
drvAsynIPPortConfigure("thermo", "$(SIM_HOST):5020")

dbLoadRecords("$(MIST2_DB)/pressure.db",        "PORT=AVR6,DEVICE=PRESSURE")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db",  "PORT=AVR6,DEVICE=PRESSURE")
dbLoadRecords("$(MIST2_DB)/sensorbox.db",       "PORT=AVR10,DEVICE=SENSOR")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db",  "PORT=AVR10,DEVICE=SENSOR")
dbLoadRecords("$(MIST2_DB)/interlockbox.db",    "PORT=AVR11,DEVICE=INTLK")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db",  "PORT=AVR11,DEVICE=INTLK")
dbLoadRecords("$(MIST2_DB)/solenoidbox.db",     "PORT=AVR12,DEVICE=VALVE")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db",  "PORT=AVR12,DEVICE=VALVE")
dbLoadRecords("$(MIST2_DB)/thermocouples.db",   "PORT=thermo,DEVICE=THM")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db",  "PORT=thermo,DEVICE=THM")

# Test only: an acknowledged set to a channel the valve box does not have (answer ERR4)
dbLoadRecords("$(CASE_DIR)/reject.db",          "PORT=AVR12")
