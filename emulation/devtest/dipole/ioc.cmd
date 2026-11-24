# ioc.cmd of the dipole case: the DAQ service over TCP, dipole.db twice on the same port:
#   dipole   drive limits 0 to 80 A, inside the service's 0 to 100 A (the normal load)
#   wide     drive limits -50 to 150 A, wider than the service's: test only, so that a set
#            beyond the service's limits reaches the service and is refused there
drvAsynIPPortConfigure("DIPOLE", "$(SIM_HOST):5000")
dbLoadRecords("$(MIST2_DB)/dipole.db",         "PORT=DIPOLE,DEVICE=dipole,DRVL=0,DRVH=80")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db", "PORT=DIPOLE,DEVICE=dipole")
dbLoadRecords("$(MIST2_DB)/first_contact.db",  "P=dipole,N=current,REQ=dipole:current:set,RB=dipole:current:held")
dbLoadRecords("$(MIST2_DB)/dipole.db",         "PORT=DIPOLE,DEVICE=wide,DRVL=-50,DRVH=150")
