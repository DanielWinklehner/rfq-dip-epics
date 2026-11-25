# ioc.cmd of the TIC case: the simulator over TCP, tic.db with its defaults (prefix and port TIC)
drvAsynIPPortConfigure("TIC", "$(SIM_HOST):5034")
dbLoadRecords("$(MIST2_DB)/tic.db", "DEVICE=TIC,PORT=TIC")
