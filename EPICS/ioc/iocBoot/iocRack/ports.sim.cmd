# ports.sim.cmd - asyn ports of the rack IOC in the emulation (MIST2_PORTS=sim)
#
# Port configuration only, one line per serial line, bus or Ethernet device. Each port goes over
# TCP to a simulator in the container sim-rack (emulation/sim/config/rack.yaml). The port names must
# equal those in ports.real.cmd, st.cmd uses them.
#
# "on error break" is needed in every file loaded with iocshLoad: the setting of st.cmd does not
# reach into this file, so without it a failing line here would not stop the startup.
on error break

# Matsusada AU supplies, optical chain behind the USB-OPT adapter (source, puller)
drvAsynIPPortConfigure("mat_opt","sim-rack:5008")

# Matsusada AU supplies, optical chain behind the CO-U32 adapter (lenses)
drvAsynIPPortConfigure("mat_co","sim-rack:5009")

# Edwards nAIM ion gauge, RS-232
drvAsynIPPortConfigure("AIM","sim-rack:5003")

# Old interlock box, Arduino, libcom1
drvAsynIPPortConfigure("AVR11","sim-rack:5011")

# Solenoid valve box, Arduino, libcom1
drvAsynIPPortConfigure("AVR12","sim-rack:5012")

# MKS GV50A mass flow controller, RS-485
drvAsynIPPortConfigure("MFC","sim-rack:5013")

# Faraday cup readout, Arduino Opta, libcom1 protocol 1 (the lab's COM16)
drvAsynIPPortConfigure("AVR16","sim-rack:5016")

# Cooling water flow meters, Arduino Opta, libcom1 protocol 1 (the lab's COM23)
drvAsynIPPortConfigure("AVR23","sim-rack:5023")

# Turbopump Opta (both NT 20), libcom1 over TCP
drvAsynIPPortConfigure("TURBO","sim-rack:5031")

# Leybold NT 20 no. 1, RS-232 data output, listen only
drvAsynIPPortConfigure("NT20_1","sim-rack:5032")

# Leybold NT 20 no. 2, RS-232 data output, listen only
drvAsynIPPortConfigure("NT20_2","sim-rack:5033")

# INFICON VGC401, the foreline gauge's controller, RS-232
drvAsynIPPortConfigure("VGC","sim-rack:5034")

# Edwards TIC station, RS-232
drvAsynIPPortConfigure("TIC","sim-rack:5035")
