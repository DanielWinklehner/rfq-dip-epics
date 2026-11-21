# ports.real.cmd - asyn ports of the HV platform IOC on the real computer (MIST2_PORTS=real)
#
# Port configuration only, one block per serial line, bus or Ethernet device. The port names
# must equal those in ports.sim.cmd, st.cmd uses them.
#
# ASSUMED, to be replaced when the real computer is set up:
#   - Device names under /dev/mist2/ (the udev rules do not exist yet).
#   - Host names of the Arduino Optas (no address plan yet).
#   - Serial settings: from the firmware or the manual of each device where they disagree with
#     the lab's old st.cmd. The differences are listed in docs/emulation/STATUS.md.
#
# "on error break" is needed in every file loaded with iocshLoad: the setting of st.cmd does not
# reach into this file, so without it a failing line here would not stop the startup.
on error break

# TDK-Lambda GENESYS 8-300, filament heating
drvAsynSerialPortConfigure("TDK","/dev/mist2/tdk")
asynSetOption("TDK",-1,"baud","19200")
asynSetOption("TDK",-1,"bits","8")
asynSetOption("TDK",-1,"parity","none")
asynSetOption("TDK",-1,"stop","1")
asynSetOption("TDK",-1,"clocal","Y")
asynSetOption("TDK",-1,"crtscts","N")

# Thermocouple board, Arduino, libcom1
drvAsynSerialPortConfigure("thermo","/dev/mist2/thermocouple")
asynSetOption("thermo",-1,"baud","19200")
asynSetOption("thermo",-1,"bits","8")
asynSetOption("thermo",-1,"parity","none")
asynSetOption("thermo",-1,"stop","1")
asynSetOption("thermo",-1,"clocal","Y")
asynSetOption("thermo",-1,"crtscts","N")
