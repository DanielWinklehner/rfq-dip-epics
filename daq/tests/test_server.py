"""The TCP side on localhost: one client at a time, the second refused or taking over, the
status port, the stream reset per client, a client that is lost."""

import json
import socket
import threading
import time
import unittest

from mist2daq import config as cfg
from mist2daq.backends import SimBackend
from mist2daq.service import Daq, Server


def start(takeover_s=10.0):
    c = cfg.parse({
        "service": {"listen_port": 0, "status_port": 0, "takeover_s": takeover_s},
        "backend": {"type": "sim"},
        "channels": [
            {"id": "o1", "name": "set", "direction": "out", "physical": "Dev1/ao0", "unit": "A",
             "per_volt": 10.0, "limits": [0, 100], "volts": [0, 10]},
            {"id": "i1", "name": "mon", "direction": "in", "physical": "Dev1/ai0", "unit": "A",
             "per_volt": 10.0, "volts": [-10, 10]},
        ]})
    backend = SimBackend(c)
    server = Server(Daq(c, backend))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread, backend


class Client:
    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=2)
        self.f = self.s.makefile("rb")

    def ask(self, line):
        self.s.sendall(line.encode() + b"\n")
        return self.f.readline().decode().rstrip("\n")

    def closed(self):
        try:
            return self.s.recv(10) == b""
        except (ConnectionResetError, socket.timeout):
            return False

    def close(self):
        self.f.close()
        self.s.close()


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.server, self.thread, self.backend = start(self.takeover)
        self.port = self.server.listener.getsockname()[1]
        self.status_port = self.server.status_listener.getsockname()[1]

    takeover = 10.0

    def tearDown(self):
        self.server.stopping = True
        self.thread.join(2)
        self.server.close()

    def status(self):
        with socket.create_connection(("127.0.0.1", self.status_port), timeout=2) as s:
            s.sendall(b'{"cmd": "status"}\n')
            return json.loads(s.makefile().readline())

    def test_conversation_and_status(self):
        a = Client(self.port)
        self.assertEqual(a.ask("I"), "oID=mist2daq;FW=mist2daq-0.1;PROTO=2;CH=o1,i1")
        self.assertEqual(a.ask("A"), "onan:0")
        self.assertEqual(a.ask("So130"), "ok")
        self.assertEqual(a.ask("A"), "o30:0")
        st = self.status()["status"]
        self.assertEqual(st["channels"]["o1"]["volts_written"], 3.0)
        self.assertEqual(st["counts"]["commands"], {"I": 1, "A": 2, "S": 1})
        self.assertEqual(st["client"].split(":")[0], "127.0.0.1")
        a.close()

    def test_status_port_is_read_only(self):
        with socket.create_connection(("127.0.0.1", self.status_port), timeout=2) as s:
            s.sendall(b'{"cmd": "set", "signal": "o1", "value": 5}\nnot json\n')
            f = s.makefile()
            self.assertFalse(json.loads(f.readline())["ok"])
            self.assertFalse(json.loads(f.readline())["ok"])
        self.assertEqual(self.backend.writes, 0)

    def test_second_client_refused_while_first_active(self):
        a = Client(self.port)
        self.assertEqual(a.ask("A"), "onan:0")
        b = Client(self.port)
        self.assertTrue(b.closed())
        self.assertEqual(a.ask("A"), "onan:0")          # the first one is not disturbed
        self.assertEqual(self.status()["status"]["clients"]["refused"], 1)
        a.close()
        b.close()

    def test_client_gone_frees_the_place_and_ends_its_stream(self):
        a = Client(self.port)
        self.assertEqual(a.ask("P50"), "ok")
        a.close()
        time.sleep(0.2)
        b = Client(self.port)
        self.assertEqual(b.ask("I")[:6], "oID=mi")
        b.s.settimeout(0.3)
        with self.assertRaises(socket.timeout):         # no frames of a's stream
            b.s.recv(100)
        b.close()

    def test_broken_long_line(self):
        a = Client(self.port)
        a.s.sendall(b"So1" + b"9" * 200 + b"\n")
        self.assertEqual(a.f.readline(), b"ERR0\n")
        a.s.sendall(b"So")                               # half a line: nothing happens
        time.sleep(0.1)
        a.s.sendall(b"15\n")
        self.assertEqual(a.f.readline(), b"ok\n")
        self.assertEqual(self.backend.writes, 1)
        a.close()


class Takeover(ServerTest):
    takeover = 0.3

    def test_second_client_replaces_a_silent_first(self):
        a = Client(self.port)
        self.assertEqual(a.ask("A"), "onan:0")
        time.sleep(0.5)
        b = Client(self.port)
        self.assertEqual(b.ask("A"), "onan:0")
        self.assertTrue(a.closed())
        self.assertEqual(self.status()["status"]["clients"]["replaced"], 1)
        a.close()
        b.close()

    test_second_client_refused_while_first_active = None


if __name__ == "__main__":
    unittest.main()
