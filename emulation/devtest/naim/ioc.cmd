# ioc.cmd of the nAIM case: the gauge simulator over TCP, aim.db as on the rack IOC
drvAsynIPPortConfigure("AIM", "$(SIM_HOST):5002")
dbLoadRecords("$(MIST2_DB)/aim.db", "DEVICE=AIM,PORT=AIM")
