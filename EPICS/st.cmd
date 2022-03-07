#!../../bin/windows-x64-mingw/sampleIOC

## You may have to change sampleIOC to something else
## everywhere it appears in this file

< envPaths
epicsEnvSet("STREAM_PROTOCOL_PATH", "$(TOP)/db")
##epicsEnvSet EPICS_CA_SERVER_PORT 8002
cd "${TOP}"

## Register all support components
dbLoadDatabase "dbd/sampleIOC.dbd"
sampleIOC_registerRecordDeviceDriver pdbbase

## Load record instances
dbLoadTemplate "db/user.substitutions"
#dbLoadRecords "db/dbSubExample.db", "user=mist-1"

# Ion gauge teensy
drvAsynSerialPortConfigure("AVR6","COM6")
asynSetOption("AVR6",-1,"baud","115200")
asynSetOption("AVR6",-1,"bits","8")
asynSetOption("AVR6",-1,"parity","even")
asynSetOption("AVR6",-1,"stop","1")
asynSetOption("AVR6",-1,"clocal","Y")
asynSetOption("AVR6",-1,"crtscts","N")
dbLoadRecords("db/IOC.pressure.db","PORT='AVR6',DEVICE=avr6")

# Interlock box mega
drvAsynSerialPortConfigure("AVR11","COM11")
asynSetOption("AVR11",-1,"baud","115200")
asynSetOption("AVR11",-1,"bits","8")
asynSetOption("AVR11",-1,"parity","none")
asynSetOption("AVR11",-1,"stop","1")
asynSetOption("AVR11",-1,"clocal","Y")
asynSetOption("AVR11",-1,"crtscts","N")
dbLoadRecords("db/IOC.interlockbox.db","PORT='AVR11',DEVICE=avr11")

# Sensor box mega
drvAsynSerialPortConfigure("AVR10","COM10")
asynSetOption("AVR10",-1,"baud","115200")
asynSetOption("AVR10",-1,"bits","8")
asynSetOption("AVR10",-1,"parity","none")
asynSetOption("AVR10",-1,"stop","1")
asynSetOption("AVR10",-1,"clocal","Y")
asynSetOption("AVR10",-1,"crtscts","N")
dbLoadRecords("db/IOC.sensorbox.db","PORT='AVR10',DEVICE=avr10")

# Solenoid valve box mega
drvAsynSerialPortConfigure("AVR12","COM12")
asynSetOption("AVR12",-1,"baud","115200")
asynSetOption("AVR12",-1,"bits","8")
asynSetOption("AVR12",-1,"parity","none")
asynSetOption("AVR12",-1,"stop","1")
asynSetOption("AVR12",-1,"clocal","Y")
asynSetOption("AVR12",-1,"crtscts","N")
dbLoadRecords("db/IOC.solenoidbox.db","PORT='AVR12',DEVICE=avr12")

# Matsusada power supplies
drvAsynSerialPortConfigure("mat_co","COM9")
asynSetOption("mat_co",-1,"baud","9600")
asynSetOption("mat_co",-1,"bits","8")
asynSetOption("mat_co",-1,"parity","none")
asynSetOption("mat_co",-1,"stop","1")
asynSetOption("mat_co",-1,"clocal","Y")
asynSetOption("mat_co",-1,"crtscts","N")
dbLoadRecords("db/matsusada_au20p7.db","PORT='mat_co',UNITNUM='1'")  # Source
dbLoadRecords("db/matsusada_au20p7.db","PORT='mat_co',UNITNUM='2'")  # Einzel Lens

drvAsynSerialPortConfigure("REK", "COM19")
asynSetOption("REK",-1,"baud","9600")
asynSetOption("REK",-1,"bits","8")
asynSetOption("REK",-1,"parity","none")
asynSetOption("REK",-1,"stop","1")
asynSetOption("REK",-1,"clocal","Y")
asynSetOption("REK",-1,"crtscts","N")
dbLoadRecords("db/rek.db","PORT='REK',UNITNUM='1'")  # Filament discharge

drvAsynSerialPortConfigure("thermo", "COM22")
asynSetOption("thermo",-1,"baud","9600")
asynSetOption("thermo",-1,"bits","8")
asynSetOption("thermo",-1,"parity","none")
asynSetOption("thermo",-1,"stop","1")
asynSetOption("thermo",-1,"clocal","Y")
asynSetOption("thermo",-1,"crtscts","N")
dbLoadRecords("db/IOC.thermocouples.db","PORT='thermo',DEVICE='thm'")  # Thermocouples

drvAsynSerialPortConfigure("AIM", "COM3")
asynSetOption("AIM",-1,"baud","9600")
asynSetOption("AIM",-1,"bits","8")
asynSetOption("AIM",-1,"parity","none")
asynSetOption("AIM",-1,"stop","1")
asynSetOption("AIM",-1,"clocal","Y")
asynSetOption("AIM",-1,"crtscts","N")
dbLoadRecords("db/IOC.aim.db","PORT='AIM',DEVICE='aim'")


drvAsynSerialPortConfigure("TDK", "COM8")
asynSetOption("TDK",-1,"baud","19200")
asynSetOption("TDK",-1,"bits","8")
asynSetOption("TDK",-1,"parity","none")
asynSetOption("TDK",-1,"stop","1")
asynSetOption("TDK",-1,"clocal","Y")
asynSetOption("TDK",-1,"crtscts","N")
dbLoadRecords("db/tdk.db","PORT='TDK',DEVICE='tdk'")  # Filament heating

#drvAsynSerialPortConfigure("MFC", "COM13")



## Set this to see messages from mySub
#var mySubDebug 1

## Run this to trace the stages of iocInit
#traceIocInit

cd "${TOP}/iocBoot/${IOC}"
iocInit

## Start any sequence programs
#seq sncExample, "user=mist-1"
