"""edwards_tic: replies of D397-30-880 Issue H, variants, the cases of a missing gauge or pump."""

import unittest

import helpers  # noqa: F401  (sys.path, quiet logging)

from mist2sim.core import ConfigError, FakeClock, build

PA_PER_TORR = 101325.0 / 760.0


def make(**options):
    sim = build({"name": "tic", "type": "edwards_tic", "port": 0, "options": options},
                clock=FakeClock())
    return sim


def ask(sim, line):
    lines = sim.process(line)
    return lines[0].decode() if lines else None


def gauge(reply):
    head, _, data = reply.partition(" ")
    value, units, state, alert, prio = data.split(";")
    return head, float(value), int(units), int(state), int(alert), int(prio)


class Tic(unittest.TestCase):
    def setUp(self):
        self.sim = make(noise=0.0, gauges=[{"pressure": 1e-6}, {"pressure": 5e-3}, None])

    def test_gauge_reading_in_pascal(self):
        reply = ask(self.sim, "?V913")
        self.assertRegex(reply, r"^=V913 \d\.\d{4}e[-+]\d\d;59;11;0;0$")
        head, value, units, state, _, _ = gauge(reply)
        self.assertAlmostEqual(value / (1e-6 * PA_PER_TORR), 1.0, places=3)
        self.assertEqual((head, units, state), ("=V913", 59, 11))
        self.assertAlmostEqual(gauge(ask(self.sim, "?V914"))[1] / (5e-3 * PA_PER_TORR), 1, places=3)

    def test_socket_without_gauge(self):
        self.assertEqual(ask(self.sim, "?V915"), "=V915 9.9000e+09;59;0;0;0")

    def test_gauge_off_striking_alert_voltage(self):
        s = self.sim.signals
        for state in (5, 6, 4):
            s["g1.state"].force(state)
            self.assertEqual(gauge(ask(self.sim, "?V913"))[1:4], (9.9e9, 59, state))
        s["g1.state"].force(11)
        s["g1.units"].force(66)
        self.assertEqual(gauge(ask(self.sim, "?V913"))[1:4], (6.546, 66, 11))

    def test_pumps_and_types(self):
        self.assertEqual(ask(self.sim, "?V904"), "=V904 4;0;0")
        self.assertEqual(ask(self.sim, "?V905"), "=V905 100.0;0;0")
        self.assertEqual(ask(self.sim, "?V910"), "=V910 4;0;0")
        self.assertEqual(ask(self.sim, "?S904 3"), "=S904 3;11")
        self.assertEqual(ask(self.sim, "?S910 3"), "=S910 3;8")
        self.assertEqual(ask(self.sim, "?S904"), "*S904 3")
        self.assertEqual(ask(self.sim, "?S904 5"), "*S904 9")
        self.sim.signals["backing.type"].force(0)
        self.assertEqual(ask(self.sim, "?S910 3"), "=S910 3;0")
        self.sim.signals["turbo.absent"].force(1)
        self.assertEqual(ask(self.sim, "?V904"), "*V904 2")
        self.assertEqual(ask(self.sim, "?V905"), "*V905 2")
        self.assertEqual(ask(self.sim, "?S904 3"), "*S904 2")

    def test_identity_and_system_status(self):
        self.assertEqual(ask(self.sim, "?S902"), "=S902 TIC100;D39700640T;000000000\x00;5.0")
        self.assertEqual(ask(self.sim, "?V902"), "=V902 4;4;11;11;0;0;0;0;0;0")

    def test_variants(self):
        self.assertEqual(len(ask(make(variant="TC", gauges=[]), "?V902")[6:].split(";")), 7)
        ic = make(variant="IC")
        self.assertEqual(len(ask(ic, "?V902")[6:].split(";")), 8)
        self.assertEqual(ask(ic, "?V904"), "*V904 2")
        self.assertEqual(ask(ic, "?S910 3"), "*S910 2")
        self.assertEqual(len(ask(make(variant="IC6"), "?V902")[6:].split(";")), 14)
        self.assertTrue(ask(make(variant="IC6"), "?V936").startswith("=V936 9.9000e+09;59;0;"))
        self.assertEqual(ask(make(variant="TC", gauges=[]), "?V913"), "*V913 2")
        self.assertEqual(ask(make(variant="IC", absent_code=1), "?V904"), "*V904 1")

    def test_other_commands_and_setups_are_counted_never_executed(self):
        self.assertEqual(ask(self.sim, "!C908 1"), "*C908 1")      # standby: not simulated
        self.assertEqual(ask(self.sim, "!S929 2"), "*S929 1")
        self.assertEqual(ask(self.sim, "!C904 2"), "*C904 4")      # not 0 or 1: out of range
        self.assertEqual(self.sim.signals["commands"].value, 3)
        self.assertEqual(ask(self.sim, "?V904"), "=V904 4;0;0")
        self.assertEqual(self.sim.stats.heads, {"!": 3, "?": 1})

    def test_framing(self):
        self.assertTrue(ask(self.sim, "xx?V9?V913").startswith("=V913 "))   # 1.2
        self.assertIsNone(ask(self.sim, "V913"))
        self.assertEqual(ask(self.sim, "?V999"), "*V999 2")
        self.assertEqual(ask(self.sim, "?V913 1"), "*V913 2")

    def test_bad_configuration(self):
        with self.assertRaises(ConfigError):
            make(variant="TPG")
        with self.assertRaises(ConfigError):
            make(variant="TC", gauges=[{"pressure": 1e-6}])
        with self.assertRaises(ConfigError):
            make(gauges=[{"pressur": 1e-6}])


APG = {"pressure": 4.0e-6, "floor_pa": 1.0e-2, "top_pa": 1.0e5}
SLAVE = {"master": 1, "on_torr": 1.0e-2, "off_torr": 2.0e-2, "enable": True}


class SixWayCross(unittest.TestCase):
    """T31, T32: the APG on socket 1 with the ends seen on the lab's TIC, the AIM on socket 2
    linked to socket 1 by the TIC's slave setup (the owner's rule: not on above 1e-2 torr), 3 s
    in the state Striking and no standing value here."""

    def setUp(self):
        self.sim = make(noise=0.01, gauges=[dict(APG), {"pressure": 2e-6, "slave": dict(SLAVE),
                                                        "strike_s": 3.0, "standing_s": 0}, None])
        self.s = self.sim.signals

    def state(self, n):
        return gauge(ask(self.sim, "?V91%d" % (2 + n)))[3]

    def test_apg_reports_exactly_its_floor_and_top_in_the_state_on(self):
        for _ in range(20):
            self.assertEqual(ask(self.sim, "?V913"), "=V913 1.0000e-02;59;11;0;0")
        self.s["g1.pressure"].force(760.0)
        for _ in range(20):
            self.assertEqual(ask(self.sim, "?V913"), "=V913 1.0000e+05;59;11;0;0")
        self.s["g1.pressure"].force(1.0)
        value = gauge(ask(self.sim, "?V913"))[1]
        self.assertAlmostEqual(value / PA_PER_TORR, 1.0, delta=0.05)

    def test_aim_follows_the_apg(self):
        clock = self.sim.clock
        self.assertEqual(self.state(2), 6)                      # APG at its floor: strikes
        clock.advance(2.9)
        self.assertEqual(self.state(2), 6)
        clock.advance(0.2)
        self.assertEqual(self.state(2), 11)
        self.assertAlmostEqual(gauge(ask(self.sim, "?V914"))[1] / (2e-6 * PA_PER_TORR), 1, delta=0.05)
        self.s["g1.pressure"].force(1.5e-2)                     # between on and off: stays on
        self.assertEqual(self.state(2), 11)
        self.s["g1.pressure"].force(2.1e-2)                     # above off: off
        self.assertEqual(ask(self.sim, "?V914"), "=V914 9.9000e+09;59;5;0;0")
        self.s["g1.pressure"].force(1.5e-2)                     # back between: stays off
        clock.advance(10)
        self.assertEqual(self.state(2), 5)
        self.s["g1.pressure"].force(1.0e-2)                     # at the owner's 1e-2 torr: strikes
        self.assertEqual(self.state(2), 6)
        self.s["g1.pressure"].force(3e-2)                       # off while striking
        self.assertEqual(self.state(2), 5)

    def test_aim_off_at_atmosphere_as_seen(self):
        sim = make(gauges=[dict(APG, pressure=760.0), {"pressure": 2e-6, "slave": dict(SLAVE)}, None])
        self.assertEqual(ask(sim, "?V914"), "=V914 9.9000e+09;59;5;0;0")
        sim.clock.advance(60)
        self.assertEqual(ask(sim, "?V914"), "=V914 9.9000e+09;59;5;0;0")
        self.assertEqual(ask(sim, "?V915"), "=V915 9.9000e+09;59;0;0;0")

    def test_aim_off_when_the_apg_is_not_on(self):
        self.assertEqual(self.state(2), 6)
        self.sim.clock.advance(5)
        self.assertEqual(self.state(2), 11)
        self.s["g1.state"].force(2)                              # New Gauge Id: no reading
        self.assertEqual(self.state(2), 5)

    def test_a_state_held_over_the_control_port_wins(self):
        self.assertEqual(self.state(2), 6)
        self.s["g2.state"].force(4)
        self.sim.clock.advance(5)
        self.assertEqual(self.state(2), 4)
        self.s["g2.state"].release()
        self.assertEqual(self.state(2), 11)

    def test_the_slave_setup_reads_back_the_link(self):
        self.assertEqual(ask(self.sim, "?S914 4"), "=S914 4;913;59;1.3332e+00;2.6664e+00;1")
        self.sim.signals["g2.slave_enable"].force(0)
        self.assertEqual(ask(self.sim, "?S914 4"), "=S914 4;913;59;1.3332e+00;2.6664e+00;0")
        self.sim.signals["g2.slave_form"].force(1)                # the manual's example form
        self.assertEqual(ask(self.sim, "?S914 4"), "=S914 913;59;1.3e+00;2.7e+00;0")
        self.assertEqual(ask(self.sim, "?S913 4"), "=S913 4;0;59;0.0000e+00;0.0000e+00;0")
        self.assertEqual(ask(self.sim, "?S915 4"), "=S915 4;0;59;0.0000e+00;0.0000e+00;0")
        self.assertEqual(ask(self.sim, "?S914 5"), "*S914 2")

    def test_not_enabled_the_link_switches_nothing(self):
        sim = make(gauges=[dict(APG), {"pressure": 2e-6, "slave": dict(SLAVE, enable=False)}, None])
        self.assertEqual(gauge(ask(sim, "?V914"))[3], 11)        # a gauge without link starts On
        sim.signals["g1.pressure"].force(760.0)
        sim.clock.advance(5)
        self.assertEqual(gauge(ask(sim, "?V914"))[3], 11)

    def test_bad_slave(self):
        for bad in ({"master": 2}, {"on_torr": 3e-2}, {"enable": 1}, {"master": 4}):
            with self.assertRaises(ConfigError):
                make(gauges=[dict(APG), {"slave": dict(SLAVE, **bad)}, None])
        with self.assertRaises(ConfigError):
            make(gauges=[dict(APG), {"slave": {"master": 1}}, None])
        with self.assertRaises(ConfigError):
            make(gauges=[dict(APG), {"strike_s": -1}, None])
        with self.assertRaises(ConfigError):
            make(gauges=[dict(APG, floor_pa=1e6)])


CART = dict(noise=0.0, turbo_type=3, turbo_state=0, turbo_speed=0.0, backing_state=0,
            gauges=[dict(APG, pressure=760.0), {"pressure": 2e-6, "state": 5}, None])


class Cart(unittest.TestCase):
    """T32: the commands to the pumps and the gauge, as the lab's controller was seen to answer
    and behave (STATUS.md, "Seen on hardware, lab session", 2026-11-25)."""

    def setUp(self):
        self.sim = make(**CART)
        self.clock = self.sim.clock

    def turbo(self):
        state = int(ask(self.sim, "?V904").split(" ")[1].split(";")[0])
        speed = float(ask(self.sim, "?V905").split(" ")[1].split(";")[0])
        return state, speed

    def backing(self):
        return int(ask(self.sim, "?V910").split(" ")[1].split(";")[0])

    def follow(self, seconds, step=1.0):
        """(seconds since now, state, speed) every `step` seconds."""
        out = []
        t = 0.0
        while t < seconds - 1e-9:
            self.clock.advance(step)
            t += step
            out.append((t,) + self.turbo())
        return out

    def test_backing_pump_on_and_off_at_once(self):
        self.assertEqual(ask(self.sim, "!C910 1"), "*C910 0")
        self.clock.advance(0.032)
        self.assertEqual(ask(self.sim, "?V910"), "=V910 4;0;0")       # seen: 4 after 32 ms
        self.assertEqual(self.turbo(), (0, 0.0))                       # the turbopump stays off
        self.assertEqual(ask(self.sim, "!C910 0"), "*C910 0")
        self.clock.advance(0.025)
        self.assertEqual(ask(self.sim, "?V910"), "=V910 0;0;0")       # seen: 0 after 25 ms

    def test_turbopump_run_up_as_seen(self):
        ask(self.sim, "!C910 1")
        self.assertEqual(ask(self.sim, "!C904 1"), "*C904 0")
        self.clock.advance(0.051)
        self.assertEqual(self.turbo()[0], 0)                           # seen: the old state at 51 ms
        trace = self.follow(130)
        states = [s for _, s, _ in trace]
        first_running = next(t for t, s, _ in trace if s == 4)
        speed_then = dict((t, v) for t, _, v in trace)
        self.assertEqual(set(states[:3]), {5})                         # Accelerating, no Starting Delay
        self.assertTrue(all(s in (5, 4) for s in states))
        self.assertTrue(all(s == 4 for s in states[states.index(4):]))
        self.assertTrue(49.0 < speed_then[first_running] < 52.0, speed_then[first_running])
        self.assertAlmostEqual(dict((t, v) for t, _, v in trace)[120.0], 100.0)
        self.assertAlmostEqual(speed_then[44.0], 50.1, places=1)       # a seen sample
        self.assertEqual(trace[-1][1:], (4, 100.0))

    def test_turbopump_run_down_with_the_backing_pump_off_105_s(self):
        sim = make(**dict(CART, turbo_state=4, turbo_speed=100.0, backing_state=4))
        self.sim, self.clock = sim, sim.clock
        self.assertEqual(ask(sim, "!C904 0"), "*C904 0")
        self.assertEqual(ask(sim, "!C910 0"), "*C910 0")               # right after, as at the lab
        self.clock.advance(0.051)
        self.assertEqual(self.turbo()[0], 4)                           # seen: still Running at 51 ms
        trace = self.follow(120)
        stopped = next(t for t, s, _ in trace if s == 0)
        self.assertTrue(all(s == 7 for t, s, _ in trace if t < stopped))
        self.assertTrue(100 <= stopped <= 106, stopped)                # seen: 0 after 105 s
        self.assertAlmostEqual(dict((t, v) for t, _, v in trace)[15.0], 57.1, delta=0.5)
        self.assertEqual(trace[-1][1:], (0, 0.0))

    def test_turbopump_run_down_with_the_backing_pump_on_is_slow(self):
        sim = make(**dict(CART, turbo_state=4, turbo_speed=100.0, backing_state=4))
        self.sim, self.clock = sim, sim.clock
        ask(sim, "!C904 0")
        trace = dict((t, (s, v)) for t, s, v in self.follow(300))
        self.assertAlmostEqual(trace[40.0][1], 49.0, places=1)         # the lead's figures
        self.assertAlmostEqual(trace[107.0][1], 16.0, places=1)
        self.assertEqual(trace[300.0], (7, 0.7))                       # still Braking after 5 min
        ask(sim, "!C910 0")                                            # backing off: the fast curve
        rest = self.follow(60)
        self.assertEqual(rest[-1][1], 0)

    def test_start_while_braking_and_without_backing_are_named_choices(self):
        sim = make(**dict(CART, turbo_state=4, turbo_speed=100.0, backing_state=4))
        self.sim, self.clock = sim, sim.clock
        ask(sim, "!C904 0")
        self.follow(20)
        speed = self.turbo()[1]
        self.assertEqual(ask(sim, "!C904 1"), "*C904 0")               # accelerate (ASSUMED)
        trace = self.follow(5)
        self.assertEqual(trace[-1][1], 4)                              # above 50 %: Running
        self.assertGreater(trace[-1][2], speed)
        refusing = make(**dict(CART, start_without_backing="refuse", start_while_braking="refuse"))
        self.assertEqual(ask(refusing, "!C904 1"), "*C904 5")          # backing off
        self.assertEqual(ask(make(**CART), "!C904 1"), "*C904 0")      # accept (ASSUMED)
        with self.assertRaises(ConfigError):
            make(**dict(CART, start_while_braking="maybe"))
        with self.assertRaises(ConfigError):
            make(**dict(CART, turbo_runup=[[0, 0], [10, 50], [5, 100]]))

    def test_gauge_on_strikes_then_stands_then_reads(self):
        sim = make(**dict(CART, gauges=[dict(APG, pressure=5e-3), {"pressure": 4e-4, "state": 5},
                                        None], noise=0.01))
        self.assertEqual(ask(sim, "?V914"), "=V914 9.9000e+09;59;5;0;0")
        self.assertEqual(ask(sim, "!C914 1"), "*C914 0")
        self.assertEqual(gauge(ask(sim, "?V914"))[3], 6)               # Striking, 0.5 s
        sim.clock.advance(0.6)
        first = ask(sim, "?V914")
        self.assertEqual(gauge(first)[3], 11)
        sim.signals["g2.pressure"].force(4e-5)                         # the cross pumps down
        for _ in range(10):
            sim.clock.advance(14.0)
            self.assertEqual(ask(sim, "?V914"), first)                 # the same value, 146 s
        sim.clock.advance(7.0)
        later = gauge(ask(sim, "?V914"))[1]
        self.assertAlmostEqual(later / (4e-5 * PA_PER_TORR), 1.0, delta=0.1)
        self.assertEqual(ask(sim, "!C914 0"), "*C914 0")
        self.assertEqual(ask(sim, "?V914"), "=V914 9.9000e+09;59;5;0;0")   # seen: Off in one step

    def test_gauge_at_the_panel_and_in_other_states(self):
        sim = make(**dict(CART, gauges=[dict(APG), {"pressure": 2e-6, "state": 5, "strike_s": 0}, None]))
        sim.signals["g2.panel"].force(1)
        self.assertEqual(gauge(ask(sim, "?V914"))[3], 11)
        sim.signals["g2.panel"].force(0)
        self.assertEqual(gauge(ask(sim, "?V914"))[3], 5)
        self.assertEqual(ask(sim, "!C915 1"), "*C915 5")               # no gauge on socket 3
        sim.signals["g2.state"].force(2)                               # New Gauge Id
        self.assertEqual(ask(sim, "!C914 1"), "*C914 5")

    def test_error_code_and_absent_pump(self):
        self.sim.signals["command_code"].force(5)
        self.assertEqual(ask(self.sim, "!C910 1"), "*C910 5")
        self.assertEqual(self.backing(), 0)                            # not executed
        self.sim.signals["command_code"].force(0)
        nopump = make(**dict(CART, backing_type=0))
        self.assertEqual(ask(nopump, "!C910 1"), "*C910 2")
        self.assertEqual(ask(self.sim, "?S904 4"), "=S904 4;0;59;0.0000e+00;0.0000e+00;0")  # seen
        self.assertEqual(self.sim.signals["commands"].value, 1)


if __name__ == "__main__":
    unittest.main()
