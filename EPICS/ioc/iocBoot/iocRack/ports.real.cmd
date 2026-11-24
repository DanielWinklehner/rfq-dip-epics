# ports.real.cmd - asyn ports of the rack IOC on the real computer (MIST2_PORTS=real)
#
# Port configuration only, one block per serial line, bus or Ethernet device. The port names
# must equal those in ports.sim.cmd, st.cmd uses them.
#
# Device names under /dev/mist2/ come from the udev rules in EPICS/ioc/host (NOT TESTED on
# hardware): by serial number, as Windows on the rack computer listed them on 2026-11-24
# (reference/lab-2026/rack-serial-devices.txt), for the gauge controller, the interlock box, the
# valve box and the MFC (99-mist2-serial.rules) and the CO-U32 (99-mist2-matsusada.rules, which
# works only if the adapter reports a serial number under Linux; Windows saw none). The other
# names (usb-opt, naim, faradaycup, flowmeters, nt20-1, nt20-2) have no rule: replace each with
# its /dev/serial/by-path/ name, found with one device plugged in at a time
# (docs/emulation/LAB-SETUP.md, section 3).
# ASSUMED, to be replaced when the real computer is set up:
#   - Host name of the turbopump Opta (no address plan yet).
#   - Serial settings: from the firmware or the manual of each device where they disagree with
#     the lab's st.cmd. The differences are listed in docs/emulation/STATUS.md. The lab's st.cmd
#     of 2026 (reference/lab-2026/EPICS/st.cmd) agrees with every line it has.
#
# "on error break" is needed in every file loaded with iocshLoad: the setting of st.cmd does not
# reach into this file, so without it a failing line here would not stop the startup.
on error break

# Matsusada AU supplies, the line on which units 1 and 2 answer (source, puller)
# Device name: EPICS/ioc/host/99-mist2-matsusada.rules, by the USB socket (no serial number)
drvAsynSerialPortConfigure("mat_opt","/dev/mist2/usb-opt")
asynSetOption("mat_opt",-1,"baud","9600")
asynSetOption("mat_opt",-1,"bits","8")
asynSetOption("mat_opt",-1,"parity","none")
asynSetOption("mat_opt",-1,"stop","1")
asynSetOption("mat_opt",-1,"clocal","Y")
asynSetOption("mat_opt",-1,"crtscts","N")

# Matsusada AU supplies, the line on which units 3 and 4 answer (lenses)
# Device name: EPICS/ioc/host/99-mist2-matsusada.rules, by the USB socket (no serial number)
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

# Gauge controller for APG and AIM, Teensy, libcom1. Even parity as in the lab's st.cmd (2023, 2026).
# Device name: EPICS/ioc/host/99-mist2-serial.rules
drvAsynSerialPortConfigure("AVR6","/dev/mist2/gauges")
asynSetOption("AVR6",-1,"baud","115200")
asynSetOption("AVR6",-1,"bits","8")
asynSetOption("AVR6",-1,"parity","even")
asynSetOption("AVR6",-1,"stop","1")
asynSetOption("AVR6",-1,"clocal","Y")
asynSetOption("AVR6",-1,"crtscts","N")

# Old interlock box, Arduino, libcom1. Device name: EPICS/ioc/host/99-mist2-serial.rules
drvAsynSerialPortConfigure("AVR11","/dev/mist2/interlock")
asynSetOption("AVR11",-1,"baud","115200")
asynSetOption("AVR11",-1,"bits","8")
asynSetOption("AVR11",-1,"parity","none")
asynSetOption("AVR11",-1,"stop","1")
asynSetOption("AVR11",-1,"clocal","Y")
asynSetOption("AVR11",-1,"crtscts","N")

# Solenoid valve box, Arduino, libcom1. Device name: EPICS/ioc/host/99-mist2-serial.rules
drvAsynSerialPortConfigure("AVR12","/dev/mist2/valves")
asynSetOption("AVR12",-1,"baud","115200")
asynSetOption("AVR12",-1,"bits","8")
asynSetOption("AVR12",-1,"parity","none")
asynSetOption("AVR12",-1,"stop","1")
asynSetOption("AVR12",-1,"clocal","Y")
asynSetOption("AVR12",-1,"crtscts","N")

# MKS GV50A mass flow controller, RS-485. Device name: EPICS/ioc/host/99-mist2-serial.rules
drvAsynSerialPortConfigure("MFC","/dev/mist2/mfc")
asynSetOption("MFC",-1,"baud","9600")
asynSetOption("MFC",-1,"bits","8")
asynSetOption("MFC",-1,"parity","none")
asynSetOption("MFC",-1,"stop","1")
asynSetOption("MFC",-1,"clocal","Y")
asynSetOption("MFC",-1,"crtscts","N")

# Faraday cup readout, Arduino Opta, libcom1 protocol 1, USB serial (the lab's COM16, 115200 8N1)
drvAsynSerialPortConfigure("AVR16","/dev/mist2/faradaycup")
asynSetOption("AVR16",-1,"baud","115200")
asynSetOption("AVR16",-1,"bits","8")
asynSetOption("AVR16",-1,"parity","none")
asynSetOption("AVR16",-1,"stop","1")
asynSetOption("AVR16",-1,"clocal","Y")
asynSetOption("AVR16",-1,"crtscts","N")

# Cooling water flow meters, Arduino Opta, libcom1 protocol 1, USB serial (the lab's COM23,
# 115200 8N1)
drvAsynSerialPortConfigure("AVR23","/dev/mist2/flowmeters")
asynSetOption("AVR23",-1,"baud","115200")
asynSetOption("AVR23",-1,"bits","8")
asynSetOption("AVR23",-1,"parity","none")
asynSetOption("AVR23",-1,"stop","1")
asynSetOption("AVR23",-1,"clocal","Y")
asynSetOption("AVR23",-1,"crtscts","N")

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
