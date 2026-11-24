# ioc.cmd of the picoammeter case: the Keithley 6485 simulator over TCP, picoammeter.db with the
# two take-overs of first_contact.db, as a real st.cmd would load them
drvAsynIPPortConfigure("PICO", "$(SIM_HOST):5001")
dbLoadRecords("$(MIST2_DB)/picoammeter.db", "DEVICE=pico1,PORT=PICO")
dbLoadRecords("$(MIST2_DB)/first_contact.db", "P=pico1,N=range,REQ=pico1:range:set,RB=pico1:_range:rb")
dbLoadRecords("$(MIST2_DB)/first_contact.db", "P=pico1,N=zcheck,REQ=pico1:zcheck:set,RB=pico1:zcheck:get")
