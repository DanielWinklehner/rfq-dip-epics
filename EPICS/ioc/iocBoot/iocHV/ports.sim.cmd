# ports.sim.cmd - asyn ports of the HV platform IOC in the emulation (MIST2_PORTS=sim)
#
# Port configuration only, one line per serial line, bus or Ethernet device. Each port goes over
# TCP to a simulator in the container sim-hv (emulation/sim/config/hv.yaml). The port names must
# equal those in ports.real.cmd, st.cmd uses them.
#
# "on error break" is needed in every file loaded with iocshLoad: the setting of st.cmd does not
# reach into this file, so without it a failing line here would not stop the startup.
on error break

# Matsusada REK150-24, filament discharge, RS-485
drvAsynIPPortConfigure("REK","sim-hv:5019")

# TDK-Lambda GENESYS 8-300, filament heating
drvAsynIPPortConfigure("TDK","sim-hv:5001")

# Thermocouple board, Arduino, libcom1
drvAsynIPPortConfigure("thermo","sim-hv:5020")
