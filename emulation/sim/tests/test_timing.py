"""Reply delay = (request + reply bytes) x bits_per_char / baud + turnaround, real sockets."""

import time
import unittest

from helpers import Echo, LineClient

from mist2sim.core import SimThread


def expected(sim, request, reply):
    chars = len(request) + len(sim.in_term) + len(reply) + len(sim.out_term)
    return chars * sim.bits_per_char / sim.baud + sim.turnaround_ms / 1000.0


class TimingTest(unittest.TestCase):
    def tolerance(self, t):
        return 0.002 + 0.02 * t

    def check_baud(self, baud, turnaround_ms):
        sim = Echo("echo", baud=baud, turnaround_ms=turnaround_ms)
        with SimThread([sim]):
            c = LineClient(sim.port)
            self.addCleanup(c.close)
            c.ask(b"warm-up")
            request = b"MEASURE-0123456789"
            per = expected(sim, request, b"re:" + request)

            # one request
            for _ in range(3):
                t0 = time.monotonic()
                self.assertEqual(c.ask(request), b"re:" + request)
                dt = time.monotonic() - t0
                self.assertAlmostEqual(dt, per, delta=self.tolerance(per),
                                       msg="single request at %d baud" % baud)

            # 20 requests back to back: reply k arrives at k x per, no drift
            t0 = time.monotonic()
            c.send((request + b"\n") * 20)
            for k in range(1, 21):
                self.assertEqual(c.readline(2.0), b"re:" + request)
                dt = time.monotonic() - t0
                self.assertAlmostEqual(dt, k * per, delta=self.tolerance(k * per),
                                       msg="reply %d of 20 at %d baud" % (k, baud))
            busy = sim.stats.busy_s
            self.assertGreater(busy, 23 * per * 0.98)

    def retry(self, check, *args):
        """Linux is not a real-time system: another process can delay one reply by tens of ms.
        Such a hiccup is not a timing error of the simulator, so a failed run is repeated (at
        most three runs). A systematic error fails all three."""
        for attempt in range(3):
            try:
                return check(*args)
            except AssertionError:
                if attempt == 2:
                    raise

    def test_9600(self):
        self.retry(self.check_baud, 9600, 5)

    def test_115200(self):
        self.retry(self.check_baud, 115200, 1)

    def test_request_without_reply_occupies_line(self):
        self.retry(self.check_quiet)

    def check_quiet(self):
        sim = Echo("echo", baud=9600)
        with SimThread([sim]):
            c = LineClient(sim.port)
            self.addCleanup(c.close)
            t0 = time.monotonic()
            c.send(b"quiet\n" * 10 + b"x\n")
            self.assertEqual(c.readline(2.0), b"re:x")
            dt = time.monotonic() - t0
            per_quiet = 6 * 10 / 9600.0
            want = 10 * per_quiet + expected(sim, b"x", b"re:x")
            self.assertAlmostEqual(dt, want, delta=self.tolerance(want))

    def test_unsolicited_output_after_reply_and_timed(self):
        self.retry(self.check_unsolicited)

    def check_unsolicited(self):
        sim = Echo("echo", baud=9600)
        with SimThread([sim]):
            c = LineClient(sim.port)
            self.addCleanup(c.close)
            t0 = time.monotonic()
            c.send(b"say\n")
            self.assertEqual(c.readline(1.0), b"said")
            t_reply = time.monotonic() - t0
            self.assertEqual(c.readline(1.0), b"unsolicited")
            t_frame = time.monotonic() - t0
            gap = len(b"unsolicited\n") * 10 / 9600.0
            self.assertAlmostEqual(t_frame - t_reply, gap, delta=self.tolerance(gap))


if __name__ == "__main__":
    unittest.main()
