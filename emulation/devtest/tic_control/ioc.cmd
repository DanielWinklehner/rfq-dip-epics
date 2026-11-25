# ioc.cmd of the TIC control case (task T32): the simulator over TCP, tic.db and tic_control.db
# with their defaults (prefix and port TIC, the gauge on socket 2), and the take-over of each
# request at the first contact, as the rack IOC loads them (iocBoot/iocRack/st.cmd)
drvAsynIPPortConfigure("TIC", "$(SIM_HOST):5034")
dbLoadRecords("$(MIST2_DB)/tic.db", "DEVICE=TIC,PORT=TIC")
dbLoadRecords("$(MIST2_DB)/tic_control.db", "DEVICE=TIC,PORT=TIC,SOCKET=2,OBJ=914")
dbLoadRecords("$(MIST2_DB)/first_contact.db", "P=TIC,N=turbo,REQ=TIC:turbo:start:set,RB=TIC:turbo:start:get")
dbLoadRecords("$(MIST2_DB)/first_contact.db", "P=TIC,N=backing,REQ=TIC:backing:start:set,RB=TIC:backing:start:get")
dbLoadRecords("$(MIST2_DB)/first_contact.db", "P=TIC,N=gauge2,REQ=TIC:gauge2:on:set,RB=TIC:gauge2:on:get")
