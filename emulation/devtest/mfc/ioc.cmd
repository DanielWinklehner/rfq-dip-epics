# ioc.cmd of the MFC case: the lab's MFC at its default address 254 on one line, and two MFCs
# with their own addresses on a second line (one bus, two prefixes)
drvAsynIPPortConfigure("MFC", "$(SIM_HOST):5000")
dbLoadRecords("$(MIST2_DB)/mfc.db", "PORT=MFC,DEVICE=MFC")
drvAsynIPPortConfigure("MFCBUS", "$(SIM_HOST):5001")
dbLoadRecords("$(MIST2_DB)/mfc.db", "PORT=MFCBUS,DEVICE=MFCA,ADDR=001")
dbLoadRecords("$(MIST2_DB)/mfc.db", "PORT=MFCBUS,DEVICE=MFCB,ADDR=002")
