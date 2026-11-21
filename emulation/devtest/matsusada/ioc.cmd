# ioc.cmd of the Matsusada case: both AU chains with the four supplies, one AU unit loaded but
# not polled (6, test only), two REK supplies (24 A and 55 A), one more REK unit whose permit PV
# does not exist, the "all off" PV, and the limits by autosave as in the IOCs' st.cmd.
drvAsynIPPortConfigure("mat_opt", "$(SIM_HOST):5001")
drvAsynIPPortConfigure("mat_co", "$(SIM_HOST):5002")
drvAsynIPPortConfigure("REK", "$(SIM_HOST):5003")
drvAsynIPPortConfigure("REK55", "$(SIM_HOST):5004")

dbLoadRecords("$(CASE_DIR)/permit.db")

dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_opt,UNITNUM=1,IFS=15")  # ion source
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_opt,UNITNUM=2")         # puller
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_co,UNITNUM=3")          # lens 1
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_co,UNITNUM=4")          # lens 2
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_co,UNITNUM=6,SCAN_MON=Passive,SCAN_GET=Passive,SCAN_STS=Passive")  # not polled
dbLoadRecords("$(MIST2_DB)/au_alloff.db", "R1=AU-20P7-1:SetToggleOutput,R2=AU-20P7-2:SetToggleOutput,R3=AU-20P7-3:SetToggleOutput,R4=AU-20P7-4:SetToggleOutput")

dbLoadRecords("$(MIST2_DB)/rek.db", "PORT=REK,UNITNUM=1")                          # filament discharge
dbLoadRecords("$(MIST2_DB)/rek.db", "PORT=REK55,UNITNUM=2,IFS=55")                 # the 55 A model
dbLoadRecords("$(MIST2_DB)/rek.db", "PORT=REK55,UNITNUM=9,PERMIT=no:such:permit,SCAN_MON=Passive,SCAN_GET=Passive,SCAN_STS=Passive")

# Limits: defaults of the case, then the file saved at run time. /tmp of the IOC container
# survives an IOC restart of the harness (same container).
set_savefile_path("/tmp")
set_requestfile_path("/tmp")
save_restoreSet_DatedBackupFiles(0)
set_pass0_restoreFile("$(CASE_DIR)/limits.defaults")
set_pass0_restoreFile("limits.sav")
afterIocRunning("makeAutosaveFileFromDbInfo /tmp/limits.req autosaveFields")
afterIocRunning("create_monitor_set limits.req 5")
