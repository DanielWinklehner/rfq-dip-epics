# ports.real.cmd - asyn ports of the rack IOC on the real computer (MIST2_PORTS=real)
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

# Matsusada AU supplies, optical chain behind the USB-OPT adapter (source, puller)
drvAsynSerialPortConfigure("mat_opt","/dev/mist2/usb-opt")
asynSetOption("mat_opt",-1,"baud","9600")
asynSetOption("mat_opt",-1,"bits","8")
asynSetOption("mat_opt",-1,"parity","none")
asynSetOption("mat_opt",-1,"stop","1")
asynSetOption("mat_opt",-1,"clocal","Y")
asynSetOption("mat_opt",-1,"crtscts","N")

# Matsusada AU supplies, optical chain behind the CO-U32 adapter (lenses)
drvAsynSerialPortConfigure("mat_co","/dev/mist2/co-u32")
asynSetOption("mat_co",-1,"baud","9600")
asynSetOption("mat_co",-1,"bits","8")
asynSetOption("mat_co",-1,"parity","none")
asynSetOption("mat_co",-1,"stop","1")
asynSetOption("mat_co",-1,"clocal","Y")
asynSetOption("mat_co",-1,"crtscts","N")

# Edwards nAIM ion gauge, RS-232
drvAsynSerialPortConfigure("AIM","/dev/mist2/naim")
asynSetOption("AIM",-1,"baud","9600")
asynSetOption("AIM",-1,"bits","8")
asynSetOption("AIM",-1,"parity","none")
asynSetOption("AIM",-1,"stop","1")
asynSetOption("AIM",-1,"clocal","Y")
asynSetOption("AIM",-1,"crtscts","N")

# Gauge controller for APG and AIM, Arduino, libcom1
drvAsynSerialPortConfigure("AVR6","/dev/mist2/gauges")
asynSetOption("AVR6",-1,"baud","115200")
asynSetOption("AVR6",-1,"bits","8")
asynSetOption("AVR6",-1,"parity","none")
asynSetOption("AVR6",-1,"stop","1")
asynSetOption("AVR6",-1,"clocal","Y")
asynSetOption("AVR6",-1,"crtscts","N")

# Sensor box (temperatures and water flows), Arduino, libcom1
drvAsynSerialPortConfigure("AVR10","/dev/mist2/sensorbox")
asynSetOption("AVR10",-1,"baud","115200")
asynSetOption("AVR10",-1,"bits","8")
asynSetOption("AVR10",-1,"parity","none")
asynSetOption("AVR10",-1,"stop","1")
asynSetOption("AVR10",-1,"clocal","Y")
asynSetOption("AVR10",-1,"crtscts","N")

# Old interlock box, Arduino, libcom1
drvAsynSerialPortConfigure("AVR11","/dev/mist2/interlock")
asynSetOption("AVR11",-1,"baud","115200")
asynSetOption("AVR11",-1,"bits","8")
asynSetOption("AVR11",-1,"parity","none")
asynSetOption("AVR11",-1,"stop","1")
asynSetOption("AVR11",-1,"clocal","Y")
asynSetOption("AVR11",-1,"crtscts","N")

# Solenoid valve box, Arduino, libcom1
drvAsynSerialPortConfigure("AVR12","/dev/mist2/valves")
asynSetOption("AVR12",-1,"baud","115200")
asynSetOption("AVR12",-1,"bits","8")
asynSetOption("AVR12",-1,"parity","none")
asynSetOption("AVR12",-1,"stop","1")
asynSetOption("AVR12",-1,"clocal","Y")
asynSetOption("AVR12",-1,"crtscts","N")

# MKS GV50A mass flow controller, RS-485
drvAsynSerialPortConfigure("MFC","/dev/mist2/mfc")
asynSetOption("MFC",-1,"baud","9600")
asynSetOption("MFC",-1,"bits","8")
asynSetOption("MFC",-1,"parity","none")
asynSetOption("MFC",-1,"stop","1")
asynSetOption("MFC",-1,"clocal","Y")
asynSetOption("MFC",-1,"crtscts","N")

# Faraday cup readout, Arduino Opta, libcom1 over TCP
drvAsynIPPortConfigure("FC","opta-fc:5025")

# Turbopump Opta (both NT 20), libcom1 over TCP
drvAsynIPPortConfigure("TURBO","opta-turbo:5025")

# Leybold NT 20 no. 1, RS-232 data output, listen only
drvAsynSerialPortConfigure("NT20_1","/dev/mist2/nt20-1")
asynSetOption("NT20_1",-1,"baud","9600")
asynSetOption("NT20_1",-1,"bits","8")
asynSetOption("NT20_1",-1,"parity","none")
asynSetOption("NT20_1",-1,"stop","1")
asynSetOption("NT20_1",-1,"clocal","Y")
asynSetOption("NT20_1",-1,"crtscts","N")

# Leybold NT 20 no. 2, RS-232 data output, listen only
drvAsynSerialPortConfigure("NT20_2","/dev/mist2/nt20-2")
asynSetOption("NT20_2",-1,"baud","9600")
asynSetOption("NT20_2",-1,"bits","8")
asynSetOption("NT20_2",-1,"parity","none")
asynSetOption("NT20_2",-1,"stop","1")
asynSetOption("NT20_2",-1,"clocal","Y")
asynSetOption("NT20_2",-1,"crtscts","N")
