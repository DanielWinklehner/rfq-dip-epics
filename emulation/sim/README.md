# mist2sim: device simulators

Every serial or TCP device of MIST-2 replaced by a program that speaks its real wire protocol
over TCP. One simulator = one TCP port = one serial line or bus. Python 3.10+, standard library
and PyYAML. Acceptance test: `emulation/sim/run_tests.sh`.

## Start one and talk to it

```
cd emulation/sim
python3 -m mist2sim --config examples/valvebox.yaml     # logs to stdout, stops on Ctrl-C / SIGTERM
printf 'I\nA\nSs11\ngs1\n' | nc -q1 localhost 5012     # device port
echo '{"cmd": "info"}' | nc -q1 localhost 6012         # control port = device port + 1000
```

Each reply is held back by the time its characters need on the real line,
`(request + reply bytes, terminators included) x bits_per_char / baud + turnaround_ms`, counted
from the arrival of the request. Requests are served one at a time in order of arrival; one that
gets no reply still occupies the line for its own length. A new connection replaces the old one.

## Configuration: a YAML list of simulators

| Key | Meaning |
|---|---|
| `name`, `type`, `port` | required. `type` is a registered type (`libcom1`, ...) |
| `control_port` | default `port + 1000` |
| `baud`, `bits_per_char`, `turnaround_ms` | line timing; defaults 9600, 10, 0 (a type can change the defaults) |
| `in_terminator`, `out_terminator` | any string, e.g. `"\r"`, `"\r\n"`, `";FF"`; default `"\n"` |
| `options` | belongs to the type, see the type's `OPTIONS` |

Unknown keys and options are errors. **libcom1** options: `identity`, `firmware`,
`number_format` (`avr` = dtostre, `g` = `%g` as on the Opta), `out_buffer` (160), `in_buffer`
(128), `comm_timeout_ms` (0 = off), `on_timeout` (`{channel: value}`), `channels` in query-all
order: `{id: s1, access: r|w|rw, behaviour: ...}`. Each channel is a signal of the same name.
Behaviours: `constant` (`value`), `analog` (`value, noise, tau, lo, hi, step`), `readback`
(reads what was written; `value, tau, lo, hi, step`), `relay` (reads 1 if exactly 1 was written,
else 0; `value`). Writes to `constant` and `analog` are accepted and ignored. libcom1 defaults:
115200 baud, in `"\n"`, out `"\r\n"` (`Serial.println`; use `"\n"` for an Opta over TCP).
Examples: `examples/valvebox.yaml`, `examples/thermocouple.yaml`.

## Control protocol: one JSON object per line, one reply per line

Every reply has `"ok": true`, or `"ok": false` and `"error"`. `unit` is optional everywhere
(default: the whole simulator). `mist2sim.control.ControlClient(host, port)` has one method per
command (`info()`, `fault(mode, unit, duration, ms)`, `clear(mode, unit)`, `get(signal)`,
`set(signal, value)`, `release(signal)`, `stats(reset)`) and `call(dict)` for raw requests.

```
{"cmd": "info"}                                   name, type, port, units, signals, settings, options
{"cmd": "fault", "mode": "silent", "unit": 2, "duration": 5}   takes input, never answers (5 s)
{"cmd": "fault", "mode": "close"}                 drops the client, refuses new ones while active
{"cmd": "fault", "mode": "garbage"}               replies corrupted, same length, correctly timed
{"cmd": "fault", "mode": "trip"}                  device specific (error if the type has none)
{"cmd": "fault", "mode": "slow", "ms": 200}       extra reply delay
{"cmd": "clear"}           {"cmd": "clear", "mode": "silent", "unit": 2}
{"cmd": "get"}             all signals {value, target, external} and the active faults
{"cmd": "get", "signal": "s1"}
{"cmd": "set", "signal": "pressure", "value": 1e-6}   held under outside control ...
{"cmd": "release", "signal": "pressure"}               ... until released
{"cmd": "stats", "reset": true}   requests, replies, bytes_in/out, busy_s, per_unit, elapsed_s
```

A silenced unit does not execute what it is sent. `get` returns true values (no noise). `stats`
counts since start or since the last `reset`; `busy_s` includes turnaround and `slow`.

## Writing a device module

Put one file in `mist2sim/devices/`. It is imported automatically; `@register("type")` makes it
usable as `type:` in a configuration. Nothing else needs editing. The base class does TCP,
framing, timing, faults, statistics and the control port. You write `setup()` and `handle()`.

* `handle(request, unit)`: `request` is bytes without the input terminator. Return `None` (no
  reply), a line, or a list of lines (bytes or str, without terminator).
* `self.add_signal(name, value, tau=, noise=, lo=, hi=, step=)`: a `Signal`. Device code writes
  `sig.target`, reads `sig.read()` (with noise) or `sig.value` (true value). Everything the plant
  model should see or drive must be a signal.
* `self.options`, `self.settings`, `self.log`, `self.now()` (seconds, from the injectable clock).
* Optional: `trip(unit)` and `trip_cleared(unit)`; `self.faulted(mode, unit)`; `tick(now)` for
  periodic work, returns the next time it wants to run (or `None`) and may call `self.send(line)`
  for unsolicited output; `self.add_coupling(fn)` with `fn(dt, signals)`, stepped before every
  request, tick and control command (example: a relay ramps a speed, the speed sets a status).
* A bus: `self.add_unit(address)` in `setup()` and `route(request)` returning a unit address,
  `ALL` (broadcast: `handle` is called for every unit) or `None`. Unknown addresses get no answer.

Minimal single-unit device:

```python
from mist2sim.core import Simulator, register

@register("demo_psu")
class DemoPSU(Simulator):
    """'V?' -> 'V=12.000', 'V 12' sets (no reply), 'OUT 1' / 'OUT 0' -> 'OK'."""
    DEFAULTS = {"baud": 9600, "in_terminator": "\r", "out_terminator": "\r"}
    OPTIONS = {"vmax": 30.0}

    def setup(self):
        self.volts = self.add_signal("volts", 0.0, tau=0.5, noise=0.002, lo=0, hi=self.options["vmax"])
        self.output = self.add_signal("output", 0.0)

    def handle(self, request, unit):
        cmd = request.decode("ascii", "replace").strip()
        if cmd == "V?":
            return "V=%.3f" % (self.volts.read() if self.output.value else 0.0)
        if cmd.startswith("V "):
            try:
                self.volts.target = float(cmd[2:])
            except ValueError:
                return "ERR"
            return None
        if cmd in ("OUT 0", "OUT 1"):
            self.output.target = float(cmd[-1])
            return "OK"
        return "ERR"

    def trip(self, unit):
        self.output.target = 0.0            # fault "trip": the output switches off
```

Minimal multi-unit bus:

```python
from mist2sim.core import ALL, Simulator, register

@register("demo_bus")
class DemoBus(Simulator):
    """'#<n> T?' -> '#<n> T=<temp>'; '#AL RST' resets every unit and nobody answers."""
    OPTIONS = {"units": [1, 2]}

    def setup(self):
        for u in self.options["units"]:
            self.add_unit(u)
            self.add_signal("%d.temp" % u, 20.0 + u, noise=0.05)

    def route(self, request):
        head = request.split(b" ", 1)[0]
        if head == b"#AL":
            return ALL
        if head[:1] == b"#" and head[1:].isdigit():
            return int(head[1:])
        return None                         # not addressed: nobody answers

    def handle(self, request, unit):
        temp = self.signals["%d.temp" % unit]
        if request.endswith(b" RST"):
            temp.target = 20.0
            return None
        if request.endswith(b" T?") and not request.startswith(b"#AL"):
            return "#%d T=%.2f" % (unit, temp.read())
        return None
```

Test it without sockets, with a fake clock, through `process()`; or with real sockets in a
background thread:

```python
from mist2sim.core import FakeClock, SimThread, build
sim = build({"name": "psu", "type": "demo_psu", "port": 0}, clock=FakeClock())
assert sim.process(b"OUT 1") == [b"OK"]
with SimThread([sim]):          # port 0: sim.port and sim.control_port are picked by the OS
    pass                        # connect to ("127.0.0.1", sim.port), ControlClient(..., sim.control_port)
```

These three examples are run by `tests/test_readme.py`.
