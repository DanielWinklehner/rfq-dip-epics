"""Example device test: read a PV, write a set point, check the IOC log."""
import os
import re
import socket
import time

import epics
import pytest

BUILD = os.environ["DEVTEST_BUILD"]

# Lines of the IOC log that mean an error (same idea as emulation/tools/ca-proof.sh)
ERROR = re.compile(r"error|can't open|not found|undefined|no such|illegal|invalid|failed|unknown"
                   r"|syntax|bad ", re.I)


def wait_for(pv, test, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        value = epics.caget(pv, timeout=1.0)
        if value is not None and test(value):
            return value
        time.sleep(0.2)
    pytest.fail("%s did not reach the expected value, last %r" % (pv, value))


def test_read_value():
    assert wait_for("EXAMPLE:value:get", lambda v: v == pytest.approx(42.5)) == pytest.approx(42.5)


def test_set_point_is_followed():
    assert epics.caput("EXAMPLE:value:set", 17.25, wait=True, timeout=5.0) == 1
    wait_for("EXAMPLE:value:get", lambda v: v == pytest.approx(17.25))
    assert epics.PV("EXAMPLE:value:set").get_ctrlvars(timeout=2)["severity"] == 0


def test_simulator_reachable_by_tcp():
    with socket.create_connection((os.environ["SIM_HOST"], 5000), timeout=2) as conn:
        conn.sendall(b"VAL?\n")
        float(conn.makefile().readline())  # a number comes back


def test_ioc_log_has_no_error_line():
    with open(os.path.join(BUILD, "ioc.log")) as handle:
        lines = [l.rstrip() for l in handle if not l.lstrip().startswith("#")]
    assert any("iocRun: All initialization complete" in l for l in lines)
    errors = [l for l in lines if ERROR.search(l) and not l.startswith("on error ")]
    assert errors == []
