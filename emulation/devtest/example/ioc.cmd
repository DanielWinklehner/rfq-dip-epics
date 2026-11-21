# ioc.cmd of the example case: one TCP port to the fake device, one database from this case
drvAsynIPPortConfigure("DEV", "$(SIM_HOST):5000")
dbLoadRecords("$(CASE_DIR)/example.db", "P=EXAMPLE,PORT=DEV")
