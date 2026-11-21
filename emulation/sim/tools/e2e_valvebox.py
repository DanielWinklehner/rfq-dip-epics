"""End-to-end check: python -m mist2sim with examples/valvebox.yaml as a subprocess, talked to
over TCP like an IOC would, with a fault injected through ControlClient."""

import os
import signal
import socket
import subprocess
import sys
import tempfile
import time

import yaml

SIM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, SIM_DIR)

from mist2sim.control import ControlClient  # noqa: E402

PORT, CONTROL = 0, 0  # set in main(): two free ports, so that parallel runs do not collide


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def config_with_free_ports():
    """examples/valvebox.yaml with its two ports replaced by free ones, as a temporary file."""
    global PORT, CONTROL
    with open(os.path.join(SIM_DIR, "examples", "valvebox.yaml")) as handle:
        entries = yaml.safe_load(handle)
    PORT, CONTROL = free_port(), free_port()
    entries[0]["port"], entries[0]["control_port"] = PORT, CONTROL
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
        yaml.safe_dump(entries, handle)
    return handle.name


def connect(port, timeout=10.0):
    end = time.monotonic() + timeout
    while True:
        try:
            return socket.create_connection(("127.0.0.1", port), timeout=1.0)
        except OSError:
            if time.monotonic() > end:
                raise
            time.sleep(0.05)


class Line:
    def __init__(self, sock):
        self.sock, self.buf = sock, b""

    def ask(self, cmd, timeout=1.0):
        self.sock.sendall(cmd + b"\n")
        self.sock.settimeout(timeout)
        while b"\r\n" not in self.buf:
            try:
                data = self.sock.recv(1024)
            except socket.timeout:
                return None
            if not data:
                raise ConnectionError("simulator closed the connection")
            self.buf += data
        line, self.buf = self.buf.split(b"\r\n", 1)
        return line


def main():
    config = config_with_free_ports()
    proc = subprocess.Popen([sys.executable, "-m", "mist2sim", "--config", config],
                            cwd=SIM_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    checks = 0
    try:
        line = Line(connect(PORT))
        expect = [
            (b"I", b"oID=SolenoidValveBox;FW=Nov 21 2026;PROTO=2;CH=s1,s2,s3,s4,s5,s6,s7,s8"),
            (b"A", b"o" + b":".join([b"+0.e+00"] * 8)),
            (b"Ss11", b"ok"),
            (b"gs1", b"o+1.e+00"),
            (b"Xyz", b"ERR0"),
        ]
        for cmd, want in expect:
            got = line.ask(cmd)
            assert got == want, "%r: expected %r, got %r" % (cmd, want, got)
            checks += 1
        with ControlClient("127.0.0.1", CONTROL) as ctl:
            ctl.fault("silent")
            got = line.ask(b"gs1", timeout=0.5)
            assert got is None, "silent fault: expected a timeout, got %r" % got
            ctl.clear()
            got = line.ask(b"gs1")
            assert got == b"o+1.e+00", "after clear: got %r" % got
            checks += 2
            stats = ctl.stats()
            assert stats["requests"] == 7 and stats["replies"] == 6, stats
            checks += 1
        print("end-to-end: %d checks passed; stats: %d requests, %d replies, %d bytes in, "
              "%d bytes out, line busy %.2f ms" % (checks, stats["requests"], stats["replies"],
                                                   stats["bytes_in"], stats["bytes_out"],
                                                   stats["busy_s"] * 1000))
    finally:
        os.unlink(config)
        proc.send_signal(signal.SIGTERM)
        try:
            out, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
    if proc.returncode != 0:
        sys.stdout.write(out.decode(errors="replace"))
        raise SystemExit("simulator exited with %s after SIGTERM" % proc.returncode)
    print("end-to-end: simulator stopped cleanly on SIGTERM")


if __name__ == "__main__":
    main()
