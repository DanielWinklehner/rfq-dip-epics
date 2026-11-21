# ioc.cmd of the Matsusada case: both AU chains, lens 3 loaded but not polled, two REK supplies
# (24 A and 55 A), one more REK unit whose permit PV does not exist, and the "all off" PV.
drvAsynIPPortConfigure("mat_opt", "$(SIM_HOST):5001")
drvAsynIPPortConfigure("mat_co", "$(SIM_HOST):5002")
drvAsynIPPortConfigure("REK", "$(SIM_HOST):5003")
drvAsynIPPortConfigure("REK55", "$(SIM_HOST):5004")

dbLoadRecords("$(CASE_DIR)/permit.db")

dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_opt,UNITNUM=1,IFS=15")  # Source
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_opt,UNITNUM=2")         # Puller
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_co,UNITNUM=3")          # Lens 1
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_co,UNITNUM=5")          # Lens 2
dbLoadRecords("$(MIST2_DB)/matsusada_au20p7.db", "PORT=mat_co,UNITNUM=4,SCAN_MON=Passive,SCAN_GET=Passive,SCAN_STS=Passive")  # Lens 3
dbLoadRecords("$(MIST2_DB)/au_alloff.db", "R1=AU-20P7-1:SetToggleOutput,R2=AU-20P7-2:SetToggleOutput,R3=AU-20P7-3:SetToggleOutput,R4=AU-20P7-5:SetToggleOutput,R5=AU-20P7-4:SetToggleOutput")

dbLoadRecords("$(MIST2_DB)/rek.db", "PORT=REK,UNITNUM=1")                          # Filament discharge
dbLoadRecords("$(MIST2_DB)/rek.db", "PORT=REK55,UNITNUM=2,IFS=55")                 # the 55 A model
dbLoadRecords("$(MIST2_DB)/rek.db", "PORT=REK55,UNITNUM=9,PERMIT=no:such:permit,SCAN_MON=Passive,SCAN_GET=Passive,SCAN_STS=Passive")
