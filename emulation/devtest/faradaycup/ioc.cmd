# ioc.cmd of the Faraday cup case: the Opta over TCP, its database and the libcom1 identity
drvAsynIPPortConfigure("FC", "$(SIM_HOST):5000")
dbLoadRecords("$(MIST2_DB)/faradaycup.db", "PORT=FC,DEVICE=FC")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db", "PORT=FC,DEVICE=FC")
