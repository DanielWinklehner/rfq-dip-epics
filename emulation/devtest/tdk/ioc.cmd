# ioc.cmd of the TDK case: the GENESYS simulator over TCP, tdk.db as on the platform IOC
drvAsynIPPortConfigure("TDK", "$(SIM_HOST):5001")
dbLoadRecords("$(MIST2_DB)/tdk.db", "DEVICE=TDK,PORT=TDK,ADR=6")
