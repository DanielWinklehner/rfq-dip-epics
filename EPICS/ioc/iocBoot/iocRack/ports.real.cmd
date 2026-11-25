# ports.real.cmd - asyn ports of the rack IOC on the real computer (MIST2_PORTS=real)
#
# Port configuration only, one block per serial line, bus or Ethernet device. The port names
# must equal those in ports.sim.cmd, st.cmd uses them.
#
# Device names under /dev/mist2/ come from the udev rules in EPICS/ioc/host: by serial number,
# as Windows on the rack computer listed them on 2026-11-24
# (reference/lab-2026/rack-serial-devices.txt), for the gauge controller, the interlock box, the
# valve box and the MFC (99-mist2-serial.rules; seen to work on the rack server for the valve
# box, the others NOT TESTED), and by USB socket for the two Matsusada adapters, which report no
# serial number (99-mist2-matsusada.rules; co-u32 and usb-opt seen to work on the rack server).
# The other names (naim, faradaycup, flowmeters, nt20-1, nt20-2, tic) have no rule: replace each with
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

# Interlock box, libcom1 on USB serial: an Arduino Opta (AVR/devices/InterlockOpta) in place of
# the lost Arduino Mega box since 2026-11-25. The baud rate means nothing to the Opta's USB port.
# Device name: EPICS/ioc/host/99-mist2-serial.rules (its line is the lost box's until the Opta's
# serial number is known; until then the name under /dev/serial/by-path/ goes here).
drvAsynSerialPortConfigure("AVR11","/dev/mist2/interlock")
asynSetOption("AVR11",-1,"baud","115200")
asynSetOption("AVR11",-1,"bits","8")
asynSetOption("AVR11",-1,"parity","none")
asynSetOption("AVR11",-1,"stop","1")
asynSetOption("AVR11",-1,"clocal","Y")
asynSetOption("AVR11",-1,"crtscts","N")

# Solenoid valve box, Arduino, libcom1. Device name: EPICS/ioc/host/99-mist2-serial.rules
# An IOC restart must not release the relays (owner, 2026-11-24). An Arduino Mega restarts, with
# all relays released, when the DTR line of its port goes from off to on. asyn opens a serial
# port with "hang up on close" (HUPCL) off (drvAsynSerialPort.c: c_cflag = CS8|CLOCAL|CREAD), so
# DTR stays on when the IOC ends and its next start makes no edge. The first open after the box
# was plugged in or the computer booted does restart the box. Any other program that opens this
# port and switches DTR (the Arduino IDE and its serial monitor) restarts it as well.
# Seen: the flag is off after this IOC had a pseudo-terminal open. NOT SEEN on the box itself.
# (The interlock box above is an Opta: it restarts only when its port is opened at 1200 baud.)
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

# INFICON VGC401, the foreline gauge's controller, RS-232, read only (T30). 9600 baud is the
# controller's default (manual tinb01e1-f p. 82); the rate is a setting of the controller.
# 8N1, no handshake (p. 55). NOT TESTED on the controller.
# Device name: EPICS/ioc/host/99-mist2-serial.rules, by the serial number of its USB adapter.
drvAsynSerialPortConfigure("VGC","/dev/mist2/vgc401")
asynSetOption("VGC",-1,"baud","9600")
asynSetOption("VGC",-1,"bits","8")
asynSetOption("VGC",-1,"parity","none")
asynSetOption("VGC",-1,"stop","1")
asynSetOption("VGC",-1,"clocal","Y")
asynSetOption("VGC",-1,"crtscts","N")

# Edwards TIC station, RS-232, read only (T29). 9600 8N1, Xon/Xoff (TIC Turbo Controller manual
# D397-12-880 2.4.5; assumed to hold for the lab's variant). NOT TESTED on the controller.
drvAsynSerialPortConfigure("TIC","/dev/mist2/tic")
asynSetOption("TIC",-1,"baud","9600")
asynSetOption("TIC",-1,"bits","8")
asynSetOption("TIC",-1,"parity","none")
asynSetOption("TIC",-1,"stop","1")
asynSetOption("TIC",-1,"clocal","Y")
asynSetOption("TIC",-1,"crtscts","N")
asynSetOption("TIC",-1,"ixon","Y")
asynSetOption("TIC",-1,"ixoff","N")
