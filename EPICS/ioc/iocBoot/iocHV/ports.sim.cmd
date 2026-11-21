# ports.sim.cmd - asyn ports of the platform (HV) IOC in the emulation (MIST2_PORTS=sim)
#
# Port configuration only, one block per bus. Each port goes over TCP to the simulator
# container sim-hv (emulation/compose.yaml). The port names must equal those in
# ports.real.cmd, st.cmd uses them.
#
# "on error break" is needed in every file loaded with iocshLoad: the setting of st.cmd does not
# reach into this file, so without it a failing line here would not stop the startup.
on error break
#
# Example:
#drvAsynIPPortConfigure("TDK","sim-hv:5001")
