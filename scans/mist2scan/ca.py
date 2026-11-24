"""The Channel Access side (pyepics): monitors, fresh reads, control limits, the one write.

Each PV is one epics.PV with form="time", so that every monitor update carries the value, its
alarm severity and the IOC's time stamp (pyepics pv.py, PV.__on_changes copies them into the
callback's arguments). The monitor mask is pyepics' default DBE_VALUE | DBE_ALARM
(ca.py, DEFAULT_SUBSCRIPTION_MASK): an alarm change arrives even when the value stays. A lost
circuit calls the connection callback with conn=False (ca.py, _onConnectionEvent ->
PV.__on_connect). Callbacks run in Channel Access' own thread (ca.py, PREEMPTIVE_CALLBACK =
True): they only hand the data to the scan, they call nothing of Channel Access.

The alarm status comes with every DBR_TIME value: ca.py, _unpack_metadata, md["status"] (the
status field of the TIME structure, dbr.py _STAT_SEV_TS); the monitor callback gets it as the
keyword "status", get_with_metadata(form="time") as md["status"]. When it is missing, the
Reading carries None and a reason says "INVALID (status not delivered)".
"""
import epics

from .engine import Reading

READ_TIMEOUT = 2.0


class Channels:
    def __init__(self, writable):
        self.writable = writable       # the only PV write() accepts: the actuator's set PV
        self.pvs = {}

    def open(self, names, on_value, on_connection):
        def value_cb(pvname=None, value=None, severity=None, timestamp=None, status=None, **kw):
            if value is not None:
                on_value(pvname, Reading(value, severity, timestamp, status))

        def connection_cb(pvname=None, conn=None, **kw):
            on_connection(pvname, bool(conn))

        for n in names:
            self.pvs[n] = epics.PV(n, form="time", auto_monitor=True, callback=value_cb,
                                   connection_callback=connection_cb)

    def wait_connected(self, names, timeout):
        """The names that are not connected after `timeout` seconds."""
        for n in names:
            self.pvs[n].wait_for_connection(timeout=timeout)
        return [n for n in names if not self.pvs[n].connected]

    def read(self, name):
        """A fresh read from the IOC (not the monitor's cache), or None."""
        pv = self.pvs[name]
        if not pv.connected:
            return None
        md = pv.get_with_metadata(use_monitor=False, timeout=READ_TIMEOUT, form="time")
        if md is None or md.get("value") is None:
            return None
        return Reading(md["value"], md.get("severity"), md.get("timestamp"), md.get("status"))

    def info(self, name):
        pv = self.pvs[name]
        if not pv.connected:
            return None
        return pv.get_ctrlvars(timeout=READ_TIMEOUT)

    def write(self, name, value):
        if name != self.writable:
            raise RuntimeError("mist2scan writes %s only, not %s" % (self.writable, name))
        pv = self.pvs[name]
        if not pv.connected:
            return False
        ok = pv.put(float(value), wait=False)     # None: the connection was lost meanwhile
        epics.ca.flush_io()
        return ok is not None

    def close(self):
        for pv in self.pvs.values():
            pv.clear_callbacks(with_connect_callback=True)
            pv.disconnect()
        self.pvs = {}
