"""The libcom1 protocol 2 device side: every command and error of AVR/libcom1/README.md, long and
broken lines, streaming, the communication timeout."""

import math
import unittest

from mist2daq.protocol import Channel, Device, LineReader, Refused, ERR_SYNTAX, f32


def make(out_buffer=None):
    state = {"o1": 0.0, "a1": 4091.71, "nan": math.nan, "timeouts": 0}

    def set_o1(v):
        state["o1"] = v

    def refuse(v):
        raise Refused(ERR_SYNTAX, "outside limits")

    channels = [
        Channel("o", 1, lambda: state["o1"], set_o1),
        Channel("a", 1, lambda: state["a1"]),
        Channel("w", 1, None, set_o1),            # write-only
        Channel("n", 1, lambda: state["nan"]),
        Channel("r", 1, lambda: 0.0, refuse),
    ]
    dev = Device(channels, "TestBox", "1.0", out_buffer=out_buffer)
    return dev, state


class Commands(unittest.TestCase):
    def setUp(self):
        self.dev, self.state = make()
        self.t = 0

    def say(self, line):
        self.t += 1
        reply, frames, code = self.dev.service(self.t, line)
        self.assertEqual(frames, [])
        return reply

    def test_query_all(self):
        self.assertEqual(self.say("A"), "o0:4091.71:0:nan:0")   # write-only reads 0, nan as nan

    def test_get(self):
        self.assertEqual(self.say("ga1"), "o4091.71")
        self.assertEqual(self.say("gn1"), "onan")

    def test_set_unacknowledged_and_acknowledged(self):
        self.assertIsNone(self.say("so112.5"))
        self.assertEqual(self.state["o1"], 12.5)
        self.assertEqual(self.say("So1-3"), "ok")
        self.assertEqual(self.say("go1"), "o-3")
        self.assertEqual(self.say("So11e3"), "ok")
        self.assertEqual(self.say("go1"), "o1000")
        self.assertEqual(self.say("So1 0.5 \r"), "ok")          # spaces around the number
        self.assertEqual(self.say("So10x1p3"), "ok")             # strtod reads hexadecimal
        self.assertEqual(self.state["o1"], 8.0)
        self.assertEqual(self.say("So12.500000"), "ok")          # what StreamDevice's %f sends
        self.assertEqual(self.state["o1"], 2.5)

    def test_set_is_rounded_to_float(self):
        self.say("So10.1")
        self.assertEqual(self.state["o1"], f32(0.1))

    def test_identity(self):
        self.assertEqual(self.say("I"), "oID=TestBox;FW=1.0;PROTO=2;CH=o1,a1,w1,n1,r1")

    def test_legacy_query(self):
        self.assertEqual(self.say("q01a13"), "oa1+40923+")       # README example
        self.assertEqual(self.say("q01a17"), "ERR1")
        self.assertEqual(self.say("q05a13"), "ERR3")
        self.assertEqual(self.say("q01a1"), "ERR5")
        self.assertEqual(self.say("q01z13"), "ERR4")
        self.assertEqual(self.say("q01w13"), "ERR7")
        self.assertEqual(self.say("q01n13"), "ERR6")              # nan
        self.say("So11e-12")
        self.assertEqual(self.say("q01o13"), "ERR6")              # exponent with two digits

    def test_errors(self):
        cases = {
            "?": "ERR0", "x": "ERR0",                             # unknown command
            "Sa15": "ERR7", "gw1": "ERR7",                        # not writable / not readable
            "gz9": "ERR4", "Sz95": "ERR4",                        # no such channel
            "So1": "ERR5", "So1abc": "ERR5", "So11.5x": "ERR5",   # malformed
            "So1nan": "ERR5", "So1inf": "ERR5", "So11e39": "ERR5",  # not finite (as a float)
            "g": "ERR5", "ga": "ERR5", "Pabc": "ERR5", "P": "ERR5", "P5x": "ERR5",
            "Sr15": "ERR5",                                       # refused by the setter
        }
        for line, expected in cases.items():
            self.assertEqual(self.say(line), expected, line)
        self.assertEqual(self.state["o1"], 0.0)                   # no rejected set was applied

    def test_unacknowledged_set_errors_are_still_answered(self):
        self.assertEqual(self.say("sz95"), "ERR4")
        self.assertEqual(self.say("so1abc"), "ERR5")

    def test_nul_ends_the_command(self):
        self.assertEqual(self.say("ga1\0junk"), "o4091.71")
        self.assertIsNone(self.say("\0A"))

    def test_identity_too_long_is_err2(self):
        dev = Device([Channel("a", 1, lambda: 1.0)], "X" * 40, "1", out_buffer=40)
        self.assertEqual(dev.service(0, "I")[0], "ERR2")


class Streaming(unittest.TestCase):
    def test_frames_and_off(self):
        dev, _ = make()
        self.assertEqual(dev.service(40, "P100")[0], "ok")
        self.assertEqual(dev.service(139)[1], [])                 # primed by the P call itself
        self.assertEqual(dev.service(140)[1], ["t0:140:0:4091.71:0:nan:0"])
        self.assertEqual(dev.service(240)[1], ["t1:240:0:4091.71:0:nan:0"])
        self.assertEqual(dev.service(900)[1], ["t2:900:0:4091.71:0:nan:0"])   # skips, no burst
        self.assertEqual(dev.service(901)[1], [])
        self.assertEqual(dev.service(1000, "P0")[0], "ok")
        self.assertEqual(dev.service(2000)[1], [])

    def test_buffer_too_small_for_streaming(self):
        dev, _ = make(out_buffer=5 * 14 + 2)
        self.assertEqual(dev.service(0, "P100")[0], "ERR2")


class CommTimeout(unittest.TestCase):
    def test_fires_once_and_clears(self):
        dev, _ = make()
        fired = []
        dev.set_comm_timeout(500, lambda: fired.append(1))
        dev.service(0, "A")
        dev.service(499)
        self.assertEqual(fired, [])
        dev.service(500)
        self.assertEqual(fired, [1])
        self.assertTrue(dev.comm_lost)
        dev.service(3000)
        self.assertEqual(fired, [1])
        dev.service(3001, "?")                    # garbage is no sign of life
        self.assertTrue(dev.comm_lost)
        dev.service(3002, "ga1")
        self.assertFalse(dev.comm_lost)
        dev.service(3502)
        self.assertEqual(fired, [1, 1])

    def test_ms_until_due(self):
        dev, _ = make()
        self.assertIsNone(dev.ms_until_due())
        dev.set_comm_timeout(500)
        dev.service(100, "A")
        self.assertEqual(dev.ms_until_due(), 500)


class Lines(unittest.TestCase):
    def test_split_lines_and_cr(self):
        r = LineReader(128)
        self.assertEqual(r.feed(b"A\r\nga"), ["A"])
        self.assertEqual(r.feed(b"1\n"), ["ga1"])
        self.assertEqual(r.feed(b"\n\r\n"), [])                   # empty lines are ignored
        self.assertEqual(r.feed(b"I\nA\n"), ["I", "A"])

    def test_long_line_is_replaced_and_answered_err0(self):
        r = LineReader(128)
        self.assertEqual(r.feed(b"S" + b"1" * 127 + b"\n"), ["!"])
        self.assertEqual(r.feed(b"S" + b"1" * 126 + b"\n"), ["S" + "1" * 126])   # 127 fit
        self.assertEqual(r.feed(b"x" * 1000), [])
        self.assertEqual(r.feed(b"x" * 1000 + b"\nA\n"), ["!", "A"])   # never executed in part
        dev, state = make()
        self.assertEqual(dev.service(0, "!")[0], "ERR0")

    def test_broken_line_without_end_is_never_executed(self):
        r = LineReader(128)
        self.assertEqual(r.feed(b"So15"), [])
        self.assertEqual(r.buf, bytearray(b"So15"))


if __name__ == "__main__":
    unittest.main()
