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
dbLoadRecords("db/IOC.pressure.db","PORT='AVR6',DEVICE=PRESSURE")

# Interlock box mega
drvAsynSerialPortConfigure("AVR11","COM11")
asynSetOption("AVR11",-1,"baud","115200")
asynSetOption("AVR11",-1,"bits","8")
asynSetOption("AVR11",-1,"parity","none")
asynSetOption("AVR11",-1,"stop","1")
asynSetOption("AVR11",-1,"clocal","Y")
asynSetOption("AVR11",-1,"crtscts","N")
dbLoadRecords("db/IOC.interlockbox.db","PORT='AVR11',DEVICE=INTLK")

# Flowmeters through OPTA
drvAsynSerialPortConfigure("AVR23","COM23")
asynSetOption("AVR23",-1,"baud","115200")
asynSetOption("AVR23",-1,"bits","8")
asynSetOption("AVR23",-1,"parity","none")
asynSetOption("AVR23",-1,"stop","1")
asynSetOption("AVR23",-1,"clocal","Y")
asynSetOption("AVR23",-1,"crtscts","N")
dbLoadRecords("db/IOC.flowmeters.db","PORT='AVR23',DEVICE=FLOW")

# FC1 through OPTA
drvAsynSerialPortConfigure("AVR16","COM16")
asynSetOption("AVR16",-1,"baud","115200")
asynSetOption("AVR16",-1,"bits","8")
asynSetOption("AVR16",-1,"parity","none")
asynSetOption("AVR16",-1,"stop","1")
asynSetOption("AVR16",-1,"clocal","Y")
asynSetOption("AVR16",-1,"crtscts","N")
dbLoadRecords("db/IOC.faraday.db","PORT='AVR16',DEVICE=FC1")

# Solenoid valve box mega
drvAsynSerialPortConfigure("AVR12","COM12")
asynSetOption("AVR12",-1,"baud","115200")
asynSetOption("AVR12",-1,"bits","8")
asynSetOption("AVR12",-1,"parity","none")
asynSetOption("AVR12",-1,"stop","1")
asynSetOption("AVR12",-1,"clocal","Y")
asynSetOption("AVR12",-1,"crtscts","N")
dbLoadRecords("db/IOC.solenoidbox.db","PORT='AVR12',DEVICE=VALVE")

# Matsusada power supplies
drvAsynSerialPortConfigure("mat_co","COM9")
asynSetOption("mat_co",-1,"baud","9600")
asynSetOption("mat_co",-1,"bits","8")
asynSetOption("mat_co",-1,"parity","none")
asynSetOption("mat_co",-1,"stop","1")
asynSetOption("mat_co",-1,"clocal","Y")
asynSetOption("mat_co",-1,"crtscts","N")
dbLoadRecords("db/matsusada_au20p7.db","PORT='mat_co',UNITNUM='2'")  # Puller
dbLoadRecords("db/matsusada_au20p7.db","PORT='mat_co',UNITNUM='3'")  # Lens 1
dbLoadRecords("db/matsusada_au20p7.db","PORT='mat_co',UNITNUM='4'")  # Lens 3

# More Matsusada power supplies (using the USB interface)
drvAsynSerialPortConfigure("mat_usb","COM7")
asynSetOption("mat_usb",-1,"baud","9600")
asynSetOption("mat_usb",-1,"bits","8")
asynSetOption("mat_usb",-1,"parity","none")
asynSetOption("mat_usb",-1,"stop","1")
asynSetOption("mat_usb",-1,"clocal","Y")
asynSetOption("mat_usb",-1,"crtscts","N")
dbLoadRecords("db/matsusada_au20p15.db","PORT='mat_usb',UNITNUM='1'")  # Source
dbLoadRecords("db/matsusada_au20p7.db","PORT='mat_usb',UNITNUM='5'")  # Lens 2

#drvAsynSerialPortConfigure("thermo", "COM22")
#asynSetOption("thermo",-1,"baud","9600")
#asynSetOption("thermo",-1,"bits","8")
#asynSetOption("thermo",-1,"parity","none")
#asynSetOption("thermo",-1,"stop","1")
#asynSetOption("thermo",-1,"clocal","Y")
#asynSetOption("thermo",-1,"crtscts","N")
#dbLoadRecords("db/IOC.thermocouples.db","PORT='thermo',DEVICE='THM'")  # Thermocouples

drvAsynSerialPortConfigure("AIM", "COM3")
asynSetOption("AIM",-1,"baud","9600")
asynSetOption("AIM",-1,"bits","8")
asynSetOption("AIM",-1,"parity","none")
asynSetOption("AIM",-1,"stop","1")
asynSetOption("AIM",-1,"clocal","Y")
asynSetOption("AIM",-1,"crtscts","N")
dbLoadRecords("db/IOC.aim.db","PORT='AIM',DEVICE='AIM'")

drvAsynSerialPortConfigure("MFC", "COM13")
asynSetOption("MFC",-1,"baud","9600")
asynSetOption("MFC",-1,"bits","8")
asynSetOption("MFC",-1,"parity","none")
asynSetOption("MFC",-1,"stop","1")
asynSetOption("MFC",-1,"clocal","Y")
asynSetOption("MFC",-1,"crtscts","N")
dbLoadRecords("db/IOC.mfc.db","PORT='MFC',DEVICE='MFC'")  # Mass Flow Controller

## Set this to see messages from mySub
#var mySubDebug 1

## Run this to trace the stages of iocInit
#traceIocInit

cd "${TOP}/iocBoot/${IOC}"
iocInit

## Start any sequence programs
#seq sncExample, "user=mist-1"
