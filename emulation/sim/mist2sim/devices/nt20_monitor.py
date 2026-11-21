"""Leybold TURBOTRONIK NT 20 frequency converter: the pump model and its RS-232 data output.

From the operating instructions GA 05.208/8 (01/97), see docs/emulation/DESIGN.md section 4:
  * started and stopped through the remote inputs (here: one Opta relay, closed = run),
  * three status relays: NORMAL (speed above 80 % of the target speed), ACCEL, FAILURE,
  * a failure is reset with the STOP command,
  * the RS-232 port only talks: "all main internal parameters" every 8 s at 9600 baud.

!!! THE RECORD FORMAT IS INVENTED. Leybold does not publish it ("more details on request"). !!!
!!! Replace format_record() below, and the protocol file EPICS/Db/nt20_monitor.proto, after  !!!
!!! a capture from a real unit. Nothing else depends on the format.                          !!!

ASSUMED (no document): rated speed, ramp and run-down times, motor currents, the braking after
a failure, and that NORMAL follows the speed also while the pump runs down after a stop.

Coupling to the Opta (a `libcom1` simulator): with options opta_port (its CONTROL port) set,
the simulator reads the run relay (`run_signal`) and writes the three contacts (`normal_signal`,
`accel_signal`, `failure_signal`) through the Opta's control interface, every `couple_s`.
Without it, `run` is a signal like any other (set it on the control port).

Signals: run (0/1, input), speed (Hz), current (A), normal, accel, failure (0/1 contacts).
Fault "trip": FAILURE closes and the pump brakes; it stays failed until run goes to 0 (STOP).
"""

import asyncio
import json

from ..core import ConfigError, Simulator, register


def format_record(speed_hz, current_a, state):
    """One line of the data output, without line ending. INVENTED placeholder format:
        NT20 f=0833Hz I=1.25A ACC
    state is one of STP (stopped), ACC (accelerating), NOR (normal), ERR (failure)."""
    return "NT20 f=%04dHz I=%.2fA %s" % (round(speed_hz), current_a, state)


@register("nt20_monitor")
class Nt20Monitor(Simulator):
    """One NT 20 controller: the pump model and the listen-only RS-232 port."""

    DEFAULTS = {"baud": 9600, "out_terminator": "\r\n"}   # ASSUMED line ending CR LF
    OPTIONS = {
        "period_s": 8.0,            # one record every 8 s (GA 05.208/8)
        "rated_speed_hz": 1200.0,   # ASSUMED (72000 rpm), depends on the pump
        "normal_fraction": 0.8,     # NORMAL above 80 % of the target speed (GA 05.208/8)
        "ramp_up_s": 120.0,         # ASSUMED time from 0 to the rated speed
        "run_down_s": 300.0,        # ASSUMED time from the rated speed to 0 after a stop
        "brake_s": 60.0,            # ASSUMED time from the rated speed to 0 after a failure
        "accel_current_a": 2.5,     # ASSUMED motor current while accelerating
        "normal_current_a": 0.6,    # ASSUMED motor current at speed
        "current_noise_a": 0.02,
        "opta_host": "127.0.0.1",   # where the Opta simulator's control port is
        "opta_port": 0,             # its control port, 0 = no coupling
        "run_signal": "r1",         # Opta relay read: 1 = run
        "normal_signal": "n1",      # Opta inputs written
        "accel_signal": "a1",
        "failure_signal": "f1",
        "couple_s": 0.25,           # exchange period with the Opta
    }

    def setup(self):
        o = self.options
        for key in ("period_s", "rated_speed_hz", "ramp_up_s", "run_down_s", "brake_s", "couple_s"):
            if o[key] <= 0:
                raise ConfigError("%s: %s must be positive" % (self.name, key))
        self.run = self.add_signal("run", 0.0)
        self.speed = self.add_signal("speed", 0.0, lo=0.0)
        self.current = self.add_signal("current", 0.0, noise=o["current_noise_a"], lo=0.0)
        self.normal = self.add_signal("normal", 0.0)
        self.accel = self.add_signal("accel", 0.0)
        self.failure = self.add_signal("failure", 0.0)
        self.failed = False
        self.next_record = 0.0
        self.coupled = False        # True after the first successful exchange with the Opta
        self.add_coupling(self._pump)

    # --- the pump model -----------------------------------------------------------------------

    def _pump(self, dt, signals):
        o = self.options
        rated = o["rated_speed_hz"]
        run = self.run.value >= 0.5
        if self.failed and not run:          # STOP resets a failure
            self.failed = False
            self.clear_faults("trip")
            self.log.info("failure reset by stop")
        speed = self.speed.value
        if self.failed:
            speed -= rated / o["brake_s"] * dt
        elif run:
            speed = min(rated, speed + rated / o["ramp_up_s"] * dt)
        else:
            speed -= rated / o["run_down_s"] * dt
        self.speed.target = max(0.0, speed)
        speed = self.speed.value
        at_speed = speed >= o["normal_fraction"] * rated
        accel = run and not self.failed and not at_speed
        self.normal.target = 1.0 if at_speed and not self.failed else 0.0
        self.accel.target = 1.0 if accel else 0.0
        self.failure.target = 1.0 if self.failed else 0.0
        self.current.target = (o["accel_current_a"] if accel else
                               o["normal_current_a"] if run and not self.failed and speed > 0 else 0.0)

    def state(self):
        if self.failed:
            return "ERR"
        if self.accel.value:
            return "ACC"
        return "NOR" if self.normal.value and self.run.value >= 0.5 else "STP"

    def trip(self, unit):
        self.failed = True
        self.step_couplings()

    # --- the RS-232 data output ---------------------------------------------------------------

    def record(self):
        return format_record(self.speed.read(), self.current.read(), self.state())

    def tick(self, now):
        if now >= self.next_record:
            self.send(self.record())
            self.next_record = now + self.options["period_s"]
        # wake often enough that the contacts follow the speed between two records
        return min(self.next_record, now + 0.1)

    # --- coupling with the Opta through its control port ---------------------------------------

    async def start(self, host="0.0.0.0"):
        await super().start(host)
        if self.options["opta_port"]:
            self._tasks.append(asyncio.ensure_future(self._exchange_loop()))

    def contacts(self):
        o = self.options
        return {o["normal_signal"]: self.normal.value, o["accel_signal"]: self.accel.value,
                o["failure_signal"]: self.failure.value}

    async def _exchange_loop(self):
        o = self.options
        while True:
            try:
                reader, writer = await asyncio.open_connection(o["opta_host"], o["opta_port"])
            except OSError as exc:
                self.log.warning("Opta control port %s:%d: %s", o["opta_host"], o["opta_port"], exc)
                await asyncio.sleep(1.0)
                continue

            async def call(req):
                writer.write((json.dumps(req) + "\n").encode())
                reply = json.loads(await reader.readline() or b"{}")
                if not reply.get("ok"):
                    raise ConnectionError("Opta control port: %s" % reply.get("error", "closed"))
                return reply

            try:
                while True:
                    reply = await call({"cmd": "get", "signal": o["run_signal"]})
                    self.run.target = 1.0 if reply["value"] >= 0.5 else 0.0
                    self.step_couplings()
                    for name, value in self.contacts().items():
                        await call({"cmd": "set", "signal": name, "value": value})
                    if not self.coupled:
                        self.coupled = True
                        self.log.info("coupled to the Opta at %s:%d", o["opta_host"], o["opta_port"])
                    await asyncio.sleep(o["couple_s"])
            except (OSError, ConnectionError, ValueError, KeyError) as exc:
                self.log.warning("exchange with the Opta failed: %s", exc)
                writer.close()
                await asyncio.sleep(1.0)
