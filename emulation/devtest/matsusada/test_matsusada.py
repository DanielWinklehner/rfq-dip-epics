"""Matsusada AU and REK databases against the matsusada_co simulator and a real IOC.

The tests run in file order: the first one needs the state in which the IOC started.
"""
import time

import pytest

# Seconds within which the :get records and read_output_status show a set or a switching (they
# are read by a forward link right after it, behind the polls of the chain).
ECHO = 3

from mat import (AU, GRACE, LENS3, LENS3_UNREAD, POLLED, SUFFIXES, WRITES, control, get, invalid,
                 ioc_seconds, put, sevr, sim_log_lines, sim_signal, switch, wait_for, all_valid)


def test_ioc_start_with_an_output_on_keeps_it_on():
    """Lens 2 (unit 5) is on in the simulator before the IOC starts, as left by a previous IOC."""
    d = "AU-20P7-5"
    wait_for(lambda: get(d + ":status:read") == 1 and get(d + ":read_output_status") == 1, 10,
             "lens 2 read as on")
    assert get(d + ":SetToggleOutput") == 1          # the request shows the supply's state
    assert get(d + ":ToggleOutput") == 1
    assert get(d + ":voltage:get") == pytest.approx(3000, abs=1)
    # past the grace period, in which the permit link connects and OutputIntlk is enabled
    wait_for(lambda: ioc_seconds() >= GRACE + 3, 15, "IOC running for GRACE + 3 s")
    assert get(d + ":OutputIntlk") == 1
    assert sim_signal(d, "output") == 1.0
    assert sim_signal(d, "vset") == pytest.approx(3000, abs=1)
    assert sim_log_lines(r"mat_co INFO unit 5:") == []    # not one set or switching command
    # the set points show the supply's settings (copied from the :get records after GRACE)
    assert get(d + ":voltage:setpoint") == pytest.approx(3000, abs=1)
    assert get(d + ":current:setpoint") == pytest.approx(7.5, abs=1e-3)
    assert sevr(d + ":voltage:setpoint") == 0 and get(d + ":voltage:setpoint.SIMM") == 0


def test_every_pv_is_valid():
    """Normal operation: every PV of every polled supply has no alarm. Lens 3 (not polled): the
    set points, their echoes (read once at the start) and the output PVs are valid; monitors,
    status and SW setting were never read (INVALID, UDF)."""
    for d in POLLED:
        wait_for(lambda: all_valid(d), 12, "%s: every PV without alarm" % d)
        assert get(d + ":OutputIntlk.STAT") == 0
    assert all_valid(LENS3, WRITES + ["voltage:get", "current:get", "_poll:tick", "_poll:gate",
                                      "_poll:done"])
    for d in POLLED:
        assert all_valid(d, ["_poll:tick", "_poll:gate", "_poll:done"])
    for pv in ("AU:alloff:set", "AU:alloff:chain1", "AU:alloff:chain2"):   # never used yet
        assert sevr(pv) == 0, pv
    for s in LENS3_UNREAD:
        assert sevr("%s:%s" % (LENS3, s)) == 3 and get("%s:%s.STAT" % (LENS3, s)) == 17, s


def test_units():
    for d in AU:
        assert get(d + ":current:read.EGU") == "mA"
    for d in ("REK-1", "REK-2"):
        for s in ("current:setpoint", "current:get", "current:read"):
            assert get("%s:%s.EGU" % (d, s)) == "A"
    assert get("AU-20P7-3:current:setpoint.DRVH") == 7.5
    assert get("AU-20P7-1:current:setpoint.DRVH") == 15
    assert get("AU-20P7-3:voltage:setpoint.DRVH") == 20000
    assert get("REK-2:current:setpoint.DRVH") == 55


@pytest.mark.parametrize("d", list(POLLED))
def test_set_points_echo_and_monitors(d):
    _, unit, vfs, ifs, load, to_a = POLLED[d]
    if get(d + ":SetToggleOutput") == 1:
        switch(d, False)
    switch(d, True)
    # The lab's toggle_output sends "ICN 100" when it switches on: the current limit is then
    # 100 % whatever current:setpoint says (documented, not changed).
    wait_for(lambda: get(d + ":current:get") == pytest.approx(ifs, rel=1e-4), ECHO,
             "%s: current setting 100 %% after switching on" % d)
    put(d + ":current:setpoint", 0.8 * ifs)
    wait_for(lambda: get(d + ":current:get") == pytest.approx(0.8 * ifs, rel=1e-4), ECHO,
             "%s: current echo" % d)
    assert sim_signal(d, "iset", "target") == pytest.approx(0.8 * ifs * to_a, rel=1e-4)
    put(d + ":voltage:setpoint", 0.5 * vfs)
    wait_for(lambda: get(d + ":voltage:get") == pytest.approx(0.5 * vfs, abs=vfs / 65535), ECHO,
             lambda: "%s: voltage echo %r %r" % (d, get(d + ":voltage:get"),
                                                 get(d + ":voltage:get.SEVR")))
    assert sevr(d + ":voltage:setpoint") == 0 and sevr(d + ":current:setpoint") == 0
    amps = 0.5 * vfs / load / to_a
    wait_for(lambda: get(d + ":voltage:read") == pytest.approx(0.5 * vfs, abs=0.002 * vfs), 3,
             "%s: voltage:read follows" % d)
    wait_for(lambda: get(d + ":current:read") == pytest.approx(amps, abs=0.002 * ifs), 3,
             "%s: current:read = V / load" % d)
    watts = 0.5 * vfs * amps * to_a
    assert get(d + ":power:read") == pytest.approx(watts, rel=0.015)
    switch(d, False)
    wait_for(lambda: get(d + ":voltage:read") < 0.002 * vfs, 3, "%s: output falls to 0" % d)
    wait_for(lambda: get(d + ":current:get") == 0, ECHO, "ICN 0 when switching off")


def test_current_limit_pulls_the_voltage_down():
    d = "AU-20P7-3"
    switch(d, True)
    put(d + ":voltage:setpoint", 16000)              # 4 mA into 4 MOhm ...
    put(d + ":current:setpoint", 1.0)                # ... limited to 1 mA: 4 kV
    wait_for(lambda: get(d + ":voltage:read") == pytest.approx(4000, abs=30), 3, "CC mode")
    wait_for(lambda: get(d + ":current:read") == pytest.approx(1.0, abs=0.01), 3, "1 mA")
    switch(d, False)


def test_echo_that_differs_raises_an_alarm():
    d = "AU-20P7-3"
    with control(d) as c:
        c.set("3.vset", 1234.0)                      # the supply keeps another setting
        try:
            put(d + ":voltage:setpoint", 5000)
            wait_for(lambda: sevr(d + ":voltage:setpoint") == 3                # INVALID,
                     and get(d + ":voltage:setpoint.STAT") == 12, 2, "CALC alarm")  # echo differs
            wait_for(lambda: get(d + ":voltage:get") == pytest.approx(1234, abs=1), ECHO,
                     "the echo shows the supply's setting")
        finally:
            c.release("3.vset")
    put(d + ":voltage:setpoint", 5000)
    assert sevr(d + ":voltage:setpoint") == 0


def test_output_switching_and_permit():
    for d in ("AU-20P7-3", "REK-1"):
        switch(d, True)
        wait_for(lambda: get(d + ":ToggleOutput") == 1 and get(d + ":read_output_status") == 1,
                 ECHO, "%s: ToggleOutput and SW setting on" % d)
        put("interlock_open", 1)                     # permit open: forced off
        wait_for(lambda: get(d + ":status:read") == 0, 3, "%s off by the permit" % d)
        assert get(d + ":ToggleOutput") == 0 and get(d + ":SetToggleOutput") == 1
        put("interlock_open", 0)                     # as in the lab: the request comes back
        wait_for(lambda: get(d + ":status:read") == 1, 3, "%s on again" % d)
        put("interlock_open.ZSV", "INVALID")         # permit INVALID with value 0: open
        put("interlock_open", 0)
        try:
            wait_for(lambda: get(d + ":status:read") == 0, 3, "%s off, permit INVALID" % d)
            assert sevr(d + ":OutputIntlk") == 3
        finally:
            put("interlock_open.ZSV", "NO_ALARM")
            put("interlock_open", 0)
        wait_for(lambda: get(d + ":status:read") == 1, 3, "%s on, permit valid" % d)
        switch(d, False)
        wait_for(lambda: get(d + ":read_output_status") == 0, ECHO, "%s: SW setting off" % d)


def test_disconnected_permit_counts_as_open():
    d = "REK-9"                                      # PERMIT=no:such:permit
    put(d + ":SetToggleOutput", 1)
    time.sleep(2)
    assert get(d + ":OutputIntlk") == 0 and sevr(d + ":OutputIntlk") == 3
    with control("rek55") as c:
        assert c.get("9.output")["value"] == 0.0
    put(d + ":SetToggleOutput", 0)


def test_trip_and_recovery():
    d = "AU-20P7-3"
    switch(d, True)
    wait_for(lambda: get(d + ":read_output_status") == 1, ECHO, "SW setting on")
    with control(d) as c:
        c.fault("trip", unit=3)
        wait_for(lambda: get(d + ":status:read") == 0, 3, "cut off visible in status:read")
        assert get(d + ":read_output_status") == 1   # SW setting still 1: the cut-off state
        c.clear("trip")
    # Recovery: a new enable. The request is still 1, so it goes 0 then 1 (a write of the value a
    # bo already has does not reach OutputIntlk, as in the lab).
    switch(d, False)
    switch(d, True)
    assert sim_signal(d, "cutoff") == 0
    switch(d, False)


def test_silent_unit_does_not_stall_its_chain():
    d, other = "AU-20P7-5", "AU-20P7-3"
    switch(other, True)
    put(other + ":voltage:setpoint", 8000)
    with control(d) as c:
        c.fault("silent", unit=5)
        t0 = time.monotonic()
        fast = wait_for(lambda: invalid(d, ["voltage:read", "current:read", "power:read",
                                            "status:read"]), 3, "monitors and status INVALID")
        wait_for(lambda: invalid(d, ["voltage:get", "current:get", "read_output_status"]), 6,
                 "echoes INVALID")
        slow = time.monotonic() - t0
        put(d + ":voltage:setpoint", 3000)           # a set to a silent supply: INVALID
        assert sevr(d + ":voltage:setpoint") == 3
        rate = monitor_rate(other + ":voltage:read", 5.0)
        print("silent unit 5: monitors INVALID after %.1f s, echoes after %.1f s; unit 3 keeps "
              "%.1f updates/s" % (fast, slow, rate))
        assert rate > 1.0                            # even share with the timeouts
        assert all_valid(other, ["voltage:read", "current:read", "status:read"])
        c.clear("silent")
    wait_for(lambda: all_valid(d, [s for s in SUFFIXES if s != "voltage:setpoint"]), 12,
             "unit 5 recovers without an IOC restart")
    put(d + ":voltage:setpoint", 3000)
    assert sevr(d + ":voltage:setpoint") == 0
    switch(other, False)


def test_closed_chain_recovers():
    with control("mat_co") as c:
        c.fault("close")
        try:
            for d in ("AU-20P7-3", "AU-20P7-5"):
                wait_for(lambda: invalid(d, ["voltage:read", "status:read"]), 5, "%s INVALID" % d)
            time.sleep(2)
        finally:
            c.clear("close")
    for d in ("AU-20P7-3", "AU-20P7-5"):
        wait_for(lambda: all_valid(d), 20, "%s recovers after the chain is back" % d)


def test_all_off():
    on = ["AU-20P7-1", "AU-20P7-2", "AU-20P7-3", "AU-20P7-5"]
    for d in on:
        if get(d + ":SetToggleOutput") == 0:
            switch(d, True)
    put(LENS3 + ":SetToggleOutput", 1)               # lens 3 can be switched, it is not polled
    wait_for(lambda: sim_signal(LENS3, "output") == 1, 3, "lens 3 on")
    t0 = time.monotonic()
    put("AU:alloff:set", 1)
    wait_for(lambda: all(sim_signal(d, "output") == 0 for d in AU), 3, "every AU output off")
    took = time.monotonic() - t0
    for d in AU:
        for s in ("SetToggleOutput", "ToggleOutput", "read_output_status"):
            wait_for(lambda: get("%s:%s" % (d, s)) == 0, ECHO, "%s:%s == 0" % (d, s))
    for d in on:
        wait_for(lambda: get(d + ":status:read") == 0, 3, "%s: status off" % d)
    print("AU:alloff:set: every output off %.0f ms after the caput" % (took * 1000))
    wait_for(lambda: get("AU:alloff:set") == 0, 3, "AU:alloff:set back to 0")
    switch("AU-20P7-3", True)                        # one write switches a supply on again
    assert sim_signal("AU-20P7-2", "output") == 0
    switch("AU-20P7-3", False)
    for d in on + [LENS3]:
        assert sevr(d + ":ToggleOutput") == 0


def test_rek_full_scale_24_and_55_A():
    put("REK-1:current:setpoint", 12)
    put("REK-2:current:setpoint", 27.5)
    assert sim_signal("REK-1", "iset", "target") == pytest.approx(12, abs=24 / 65535)
    assert sim_signal("REK-2", "iset", "target") == pytest.approx(27.5, abs=55 / 65535)
    with control("rek55") as c:
        assert c.get("2.iset")["target"] / 55 == pytest.approx(0x8000 / 0xFFFF, abs=1e-6)
    assert get("REK-2:current:get") == pytest.approx(27.5, abs=55 / 65535)


def monitor_rate(pv, seconds):
    """Updates per second a Channel Access client sees (MDEL -1 for the measurement, so that
    every processing is posted, also an unchanged value)."""
    import epics
    put(pv + ".MDEL", -1)
    count = [0]
    mon = epics.PV(pv, callback=lambda **kw: count.__setitem__(0, count[0] + 1))
    mon.wait_for_connection(3)
    time.sleep(0.5)
    count[0] = 0
    time.sleep(seconds)
    n = count[0]
    mon.clear_callbacks()
    mon.disconnect()
    put(pv + ".MDEL", 0)
    return n / seconds
