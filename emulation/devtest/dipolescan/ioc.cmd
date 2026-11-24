# ioc.cmd of the dipolescan case: the dipole supply through the DAQ service and the picoammeter,
# in one IOC, each with the loads its database header names. Drive limits 0-100 A = the service's
# limits (dipole.db header: DRVL/DRVH equal to the service's limits or within them).
drvAsynIPPortConfigure("DIPOLE", "$(SIM_HOST):5000")
dbLoadRecords("$(MIST2_DB)/dipole.db",         "PORT=DIPOLE,DEVICE=dipole,DRVL=0,DRVH=100")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db", "PORT=DIPOLE,DEVICE=dipole")
dbLoadRecords("$(MIST2_DB)/first_contact.db",  "P=dipole,N=current,REQ=dipole:current:set,RB=dipole:current:held")
drvAsynIPPortConfigure("PICO", "$(SIM_HOST):5001")
dbLoadRecords("$(MIST2_DB)/picoammeter.db",    "DEVICE=pico1,PORT=PICO")
dbLoadRecords("$(MIST2_DB)/first_contact.db",  "P=pico1,N=range,REQ=pico1:range:set,RB=pico1:_range:rb")
dbLoadRecords("$(MIST2_DB)/first_contact.db",  "P=pico1,N=zcheck,REQ=pico1:zcheck:set,RB=pico1:zcheck:get")
