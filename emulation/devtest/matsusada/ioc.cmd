# ioc.cmd of the Matsusada case: both AU chains with the four supplies, one AU unit loaded but
# not polled (6, test only), two REK supplies (24 A and 55 A), one more REK unit whose permit PV
# does not exist, the "all off" PV, and the limits by autosave as in the IOCs' st.cmd. Two asyn
# records (line trace for test_permit_enforce.py and test_switch_resend.py), two more lines for
# test_stray_reply.py (task T22) with their asyn records, and the helper that
# writes into a busy ToggleOutput without the put flag (lost_write.db, test_switch_resend.py).
drvAsynIPPortConfigure("mat_opt", "$(SIM_HOST):5001")
drvAsynIPPortConfigure("mat_co", "$(SIM_HOST):5002")
drvAsynIPPortConfigure("REK", "$(SIM_HOST):5003")
drvAsynIPPortConfigure("REK55", "$(SIM_HOST):5004")
drvAsynIPPortConfigure("mat_late", "$(SIM_HOST):5005")
drvAsynIPPortConfigure("mat_bang", "$(SIM_HOST):5006")

dbLoadRecords("$(CASE_DIR)/permit.db")

# asyn records of two ports, for test_permit_enforce.py: it switches on the trace of what the IOC
# writes to the line (traceIOMask) while it watches a supply, so that REN, which the simulator
# logs only when it takes control back from the front panel, can be seen.
dbLoadRecords("/opt/epics/support/asyn/db/asynRecord.db", "P=DEVTEST:,R=asyn:mat_co,PORT=mat_co,ADDR=0,OMAX=80,IMAX=80")
dbLoadRecords("/opt/epics/support/asyn/db/asynRecord.db", "P=DEVTEST:,R=asyn:REK,PORT=REK,ADDR=0,OMAX=80,IMAX=80")
dbLoadRecords("/opt/epics/support/asyn/db/asynRecord.db", "P=DEVTEST:,R=asyn:mat_late,PORT=mat_late,ADDR=0,OMAX=80,IMAX=80")
dbLoadRecords("/opt/epics/support/asyn/db/asynRecord.db", "P=DEVTEST:,R=asyn:mat_bang,PORT=mat_bang,ADDR=0,OMAX=80,IMAX=80")

dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_opt,UNITNUM=1,IFS=15")  # ion source
dbLoadRecords("$(MIST2_DB)/supply_first_contact.db", "S=AU-20P7-1")
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_opt,UNITNUM=2")         # puller
dbLoadRecords("$(MIST2_DB)/supply_first_contact.db", "S=AU-20P7-2")
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_co,UNITNUM=3")          # lens 1
dbLoadRecords("$(MIST2_DB)/supply_first_contact.db", "S=AU-20P7-3")
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_co,UNITNUM=4")          # lens 2
dbLoadRecords("$(MIST2_DB)/supply_first_contact.db", "S=AU-20P7-4")
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_co,UNITNUM=6,SCAN_MON=Passive,SCAN_GET=Passive,SCAN_STS=Passive")  # not polled
dbLoadRecords("$(MIST2_DB)/supply_first_contact.db", "S=AU-20P7-6")
dbLoadRecords("$(MIST2_DB)/au_alloff.db", "R1=AU-20P7-1:SetToggleOutput,R2=AU-20P7-2:SetToggleOutput,R3=AU-20P7-3:SetToggleOutput,R4=AU-20P7-4:SetToggleOutput")

dbLoadRecords("$(MIST2_DB)/rek.db", "PORT=REK,UNITNUM=1")                          # filament discharge
dbLoadRecords("$(MIST2_DB)/supply_first_contact.db", "S=REK-1")
dbLoadRecords("$(MIST2_DB)/rek.db", "PORT=REK55,UNITNUM=2,IFS=55")                 # the 55 A model
dbLoadRecords("$(MIST2_DB)/supply_first_contact.db", "S=REK-2")
dbLoadRecords("$(MIST2_DB)/rek.db", "PORT=REK55,UNITNUM=9,PERMIT=no:such:permit,SCAN_MON=Passive,SCAN_GET=Passive,SCAN_STS=Passive")
dbLoadRecords("$(MIST2_DB)/supply_first_contact.db", "S=REK-9")

# Task T22 (P49), test_stray_reply.py only: the lines mat_late (two polled supplies, a third
# loaded but not polled) and mat_bang (units that send "!" when their output goes off), with the
# same databases and defaults as the rack's supplies.
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_late,DEV=LATE,UNITNUM=1")
dbLoadRecords("$(MIST2_DB)/supply_first_contact.db", "S=LATE-1")
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_late,DEV=LATE,UNITNUM=2")
dbLoadRecords("$(MIST2_DB)/supply_first_contact.db", "S=LATE-2")
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_late,DEV=LATE,UNITNUM=3,SCAN_MON=Passive,SCAN_GET=Passive,SCAN_STS=Passive")
dbLoadRecords("$(MIST2_DB)/supply_first_contact.db", "S=LATE-3")
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_bang,DEV=BANG,UNITNUM=1")
dbLoadRecords("$(MIST2_DB)/supply_first_contact.db", "S=BANG-1")
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_bang,DEV=BANG,UNITNUM=2")
dbLoadRecords("$(MIST2_DB)/supply_first_contact.db", "S=BANG-2")

# Test helper of test_switch_resend.py (this case only): writes into ToggleOutput from a periodic
# scan, so that a write into the busy record carries no put flag, as the gate's own scan does.
dbLoadRecords("$(CASE_DIR)/lost_write.db", "S=AU-20P7-3")
dbLoadRecords("$(CASE_DIR)/lost_write.db", "S=REK-1")

# Limits: defaults of the case, then the file saved at run time. /tmp of the IOC container
# survives an IOC restart of the harness (same container).
set_savefile_path("/tmp")
set_requestfile_path("/tmp")
save_restoreSet_DatedBackupFiles(0)
set_pass0_restoreFile("$(CASE_DIR)/limits.defaults")
set_pass0_restoreFile("limits.sav")
afterIocRunning("makeAutosaveFileFromDbInfo /tmp/limits.req autosaveFields")
afterIocRunning("create_monitor_set limits.req 5")
