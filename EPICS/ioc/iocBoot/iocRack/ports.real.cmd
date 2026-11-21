# ports.real.cmd - asyn ports of the rack IOC on the real computer (MIST2_PORTS=real)
#
# Port configuration only, one block per bus. The port names must equal those in
# ports.sim.cmd, st.cmd uses them. Device names under /dev/mist2/ are placeholders until
# the udev rules exist.
#
# Example (19200 baud, 8N1):
#drvAsynSerialPortConfigure("TDK","/dev/mist2/tdk")
#asynSetOption("TDK",-1,"baud","19200")
#asynSetOption("TDK",-1,"bits","8")
#asynSetOption("TDK",-1,"parity","none")
#asynSetOption("TDK",-1,"stop","1")
#asynSetOption("TDK",-1,"clocal","Y")
#asynSetOption("TDK",-1,"crtscts","N")
