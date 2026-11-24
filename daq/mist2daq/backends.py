"""The two backends behind one small interface: volts in, volts out, by physical channel name.

    open()                    prepare; writes NO output
    write(physical, volts)    set one analog output; raises BackendError when it did not happen
    read_inputs()             {physical: volts} of every input, one sample each; raises BackendError
    outputs_written()         {physical: volts} written by this process (for the status port)
    close()                   release the hardware; writes NO output

`sim` keeps everything in memory. `nidaqmx` drives an NI box through NI's Python package; it is
written from NI's documentation and has NOT BEEN RUN against hardware (docs/emulation/DAQ.md).
"""

import math
import time


class BackendError(Exception):
    pass


class Backend:
    def __init__(self, config):
        self.config = config
        self._written = {}

    def open(self):
        pass

    def write(self, physical, volts):
        raise NotImplementedError

    def read_inputs(self):
        raise NotImplementedError

    def outputs_written(self):
        return dict(self._written)

    def close(self):
        pass


# --- sim ----------------------------------------------------------------------------------------

SIM_INPUT_KEYS = {"follow", "gain", "tau_s", "offset_v", "volts"}


class SimBackend(Backend):
    """In memory. An input can follow an output: volts = gain * output + offset_v, through a
    first-order lag with time constant tau_s (a supply's current monitor). An input that follows
    nothing reads its fixed `volts`. Every output starts at `initial_volts` (default 0 V: the
    power-on state of the USB-6001's analog outputs in NI's specifications)."""

    def __init__(self, config, clock=time.monotonic):
        super().__init__(config)
        self.clock = clock
        opts = config.backend.get("sim") or {}
        if not isinstance(opts, dict):
            raise BackendError("backend.sim: expected a mapping")
        extra = sorted(set(opts) - {"initial_volts", "inputs"})
        if extra:
            raise BackendError("backend.sim: unknown key(s) %s" % ", ".join(extra))
        outs = [c.physical for c in config.outputs]
        ins = [c.physical for c in config.inputs]
        initial = opts.get("initial_volts") or {}
        for name in initial:
            if name not in outs:
                raise BackendError("backend.sim.initial_volts: %s is not an output" % name)
        self.out = {p: float(initial.get(p, 0.0)) for p in outs}
        self.models = {}
        for p in ins:
            m = dict((opts.get("inputs") or {}).get(p) or {})
            extra = sorted(set(m) - SIM_INPUT_KEYS)
            if extra:
                raise BackendError("backend.sim.inputs.%s: unknown key(s) %s" % (p, ", ".join(extra)))
            if "follow" in m and m["follow"] not in outs:
                raise BackendError("backend.sim.inputs.%s: follow %r is not an output" % (p, m["follow"]))
            m.setdefault("gain", 1.0)
            m.setdefault("tau_s", 0.0)
            m.setdefault("offset_v", 0.0)
            m.setdefault("volts", 0.0)
            m["state"] = self._target(m)
            self.models[p] = m
        unknown = sorted(set(opts.get("inputs") or {}) - set(ins))
        if unknown:
            raise BackendError("backend.sim.inputs: %s are not inputs" % ", ".join(unknown))
        self.last = self.clock()
        self.fail_writes = False        # tests: the next writes fail as a broken USB link would
        self.writes = 0

    def _target(self, m):
        if "follow" in m:
            return m["gain"] * self.out[m["follow"]] + m["offset_v"]
        return m["volts"]

    def _advance(self):
        now = self.clock()
        dt = max(0.0, now - self.last)
        self.last = now
        for m in self.models.values():
            target = self._target(m)
            if m["tau_s"] > 0:
                m["state"] += (target - m["state"]) * (1.0 - math.exp(-dt / m["tau_s"]))
            else:
                m["state"] = target

    def write(self, physical, volts):
        self._advance()                 # the lag runs with the old output up to now
        if self.fail_writes:
            raise BackendError("sim: write to %s failed (test)" % physical)
        self.out[physical] = float(volts)
        self._written[physical] = float(volts)
        self.writes += 1

    def read_inputs(self):
        self._advance()
        return {p: m["state"] for p, m in self.models.items()}

    def state(self):
        return {"outputs_v": dict(self.out), "writes": self.writes,
                "inputs_v": {p: m["state"] for p, m in self.models.items()}}


# --- nidaqmx ------------------------------------------------------------------------------------
#
# NOT VERIFIED: written from the documentation of NI's Python package nidaqmx 1.7.0 (the
# docstrings of the package as published on PyPI, the same text as nidaqmx-python.readthedocs.io)
# and never run against an NI box. Sources, per call:
#   nidaqmx.Task(new_task_name="")                         nidaqmx/task/_task.py, Task.__init__
#   task.ao_channels.add_ao_voltage_chan(physical_channel, name_to_assign_to_channel="",
#       min_val=-10.0, max_val=10.0, ...)                  nidaqmx/task/collections/_ao_channel_collection.py
#   task.ai_channels.add_ai_voltage_chan(physical_channel, name_to_assign_to_channel="",
#       terminal_config=TerminalConfiguration.DEFAULT, min_val=-5.0, max_val=5.0, ...)
#                                                          nidaqmx/task/collections/_ai_channel_collection.py
#   nidaqmx.constants.TerminalConfiguration.{DEFAULT,RSE,NRSE,DIFF}   nidaqmx/constants.py
#   task.write(data, auto_start=..., timeout=10.0): on-demand timing (the default) returns after
#       the sample was generated                           nidaqmx/task/_task.py, Task.write
#   task.read(number_of_samples_per_channel unset, timeout=10.0): one sample, a scalar for one
#       channel, a list for N channels                     nidaqmx/task/_task.py, Task.read
#   task.close(): alias of clear(): aborts the task and releases its resources
#                                                          nidaqmx/task/_task.py, Task.close/clear
#   nidaqmx.system.System.local().devices[name].product_type          nidaqmx/system/system.py, device.py
#   nidaqmx.errors.Error, base of DaqError and DaqNotFoundError (no NI-DAQmx installed)
#                                                          nidaqmx/errors.py
# What NI's documentation does not say (as far as read): whether an analog output keeps its last
# value after its task is cleared, and whether two analog output tasks may run at the same time
# on a USB-6001. Both matter here and are open points (docs/emulation/DAQ.md).


class NidaqmxBackend(Backend):
    """One AI task with every input; one AO task per output, created at the first write of that
    output (so that nothing is configured on an output this process has not been asked to set)."""

    def __init__(self, config):
        super().__init__(config)
        try:
            import nidaqmx                      # only this backend needs it
            import nidaqmx.errors               # noqa: F401
            import nidaqmx.system               # noqa: F401
            from nidaqmx.constants import TerminalConfiguration
        except ImportError as exc:
            raise BackendError("backend nidaqmx: the Python package nidaqmx is not installed (%s)" % exc)
        self.nidaqmx = nidaqmx
        self.terminal = TerminalConfiguration
        self.ai_task = None
        self.ai_order = []
        self.ao_tasks = {}
        self.by_physical = {c.physical: c for c in config.channels}

    def _call(self, what, fn, *args, **kw):
        try:
            return fn(*args, **kw)
        except self.nidaqmx.errors.Error as exc:   # DaqError, and DaqNotFoundError (no driver)
            raise BackendError("%s: %s" % (what, exc)) from None

    def open(self):
        device = self.config.backend.get("device")
        expected = self.config.backend.get("product_type")
        if device:
            system = self._call("System.local", self.nidaqmx.system.System.local)
            names = [d.name for d in system.devices]
            if device not in names:
                raise BackendError("NI device %r not found; NI-DAQmx sees %s" % (device, names or "none"))
            product = system.devices[device].product_type
            if expected and product != expected:
                raise BackendError("NI device %r is a %s, the configuration expects %s" % (device, product, expected))
        inputs = self.config.inputs
        if inputs:
            self.ai_task = self._call("Task", self.nidaqmx.Task, "mist2daq-ai")
            for c in inputs:
                self._call("add_ai_voltage_chan %s" % c.physical, self.ai_task.ai_channels.add_ai_voltage_chan,
                           c.physical, terminal_config=getattr(self.terminal, c.terminal),
                           min_val=c.volts[0], max_val=c.volts[1])
                self.ai_order.append(c.physical)

    def _ao_task(self, physical):
        task = self.ao_tasks.get(physical)
        if task is None:
            c = self.by_physical[physical]
            task = self._call("Task", self.nidaqmx.Task, "mist2daq-ao-%s" % c.id)
            try:
                self._call("add_ao_voltage_chan %s" % physical, task.ao_channels.add_ao_voltage_chan,
                           physical, min_val=c.volts[0], max_val=c.volts[1])
            except BackendError:
                task.close()
                raise
            self.ao_tasks[physical] = task
        return task

    def write(self, physical, volts):
        task = self._ao_task(physical)
        self._call("write %s" % physical, task.write, float(volts), auto_start=True, timeout=2.0)
        self._written[physical] = float(volts)

    def read_inputs(self):
        if self.ai_task is None:
            return {}
        data = self._call("read", self.ai_task.read, timeout=2.0)
        if len(self.ai_order) == 1:
            data = [data]
        return {p: float(v) for p, v in zip(self.ai_order, data)}

    def close(self):
        # Clears the tasks only; writes nothing. What the outputs do afterwards: see DAQ.md.
        for task in list(self.ao_tasks.values()) + ([self.ai_task] if self.ai_task else []):
            try:
                task.close()
            except Exception:           # closing is best effort at shutdown
                pass
        self.ao_tasks, self.ai_task = {}, None


def make_backend(config, clock=time.monotonic):
    kind = config.backend["type"]
    if kind == "sim":
        return SimBackend(config, clock)
    return NidaqmxBackend(config)
