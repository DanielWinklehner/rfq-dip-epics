# ioc.cmd of the Faraday cup case: the lab's FC1 (reference/lab-2026: IOC.faraday.db on COM16), an
# Opta with libcom1 protocol 1 as flashed. No libcom1_device.db: its identity queries need protocol 2.
drvAsynIPPortConfigure("AVR16", "$(SIM_HOST):5000")
dbLoadRecords("$(MIST2_DB)/faradaycup.db", "PORT=AVR16,DEVICE=FC1")
