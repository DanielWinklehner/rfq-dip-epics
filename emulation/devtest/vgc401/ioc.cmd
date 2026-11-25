# ioc.cmd of the VGC401 case: the controller simulator over TCP, vgc401.db as on the rack IOC
drvAsynIPPortConfigure("VGC", "$(SIM_HOST):5034")
dbLoadRecords("$(MIST2_DB)/vgc401.db", "DEVICE=FORELINE,PORT=VGC")
