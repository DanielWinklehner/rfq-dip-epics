# ioc.cmd of the flow meter case: the lab's FLOW (reference/lab-2026: IOC.flowmeters.db on COM23),
# an Opta with FlowMeters.ino, libcom1 protocol 1. No libcom1_device.db: its identity queries need
# protocol 2.
drvAsynIPPortConfigure("AVR23", "$(SIM_HOST):5000")
dbLoadRecords("$(MIST2_DB)/flowmeters.db", "PORT=AVR23,DEVICE=FLOW")
