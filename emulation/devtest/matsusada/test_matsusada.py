"""Matsusada AU and REK databases against the matsusada_co simulator and a real IOC.

The tests run in file order: the first two need the state in which the IOC started.
"""
import time

import pytest

from mat import (AU, GRACE, INTERNAL, POLLED, SUFFIXES, UNPOLLED, UNPOLLED_UNREAD, WRITES,
                 all_valid, control, get, invalid, ioc_seconds, not_valid, put, restart_ioc,
                 sevr,
                 sim_log_lines, sim_log_mark, sim_log_since, sim_signal, switch, wait_for)

# Seconds within which the :get records and read_output_status show a set or a switching (they
# are read by a forward link right after it, behind the polls of the chain).
ECHO = 3
# Lines of the simulator log for a set or switching command executed by a unit (CH1 is the
# current limit, which the IOC sends at the first contact).
CMD = r"%s INFO unit %d: (CH0|SW|RST|VCN|ICN)"


def test_ioc_start_with_an_output_on_keeps_it_on():
    """Lens 2 (unit 4) is on in the simulator before the IOC starts, as left by a previous IOC."""
    d = "AU-20P7-4"
    wait_for(lambda: get(d + ":status:read") == 1 and get(d + ":read_output_status") == 1, 10,
             "lens 2 read as on")
    assert get(d + ":SetToggleOutput") == 1          # the request shows the supply's state
    assert get(d + ":ToggleOutput") == 1
    assert get(d + ":voltage:get") == pytest.approx(3000, abs=1)
    wait_for(lambda: ioc_seconds() >= GRACE + 3, 15, "IOC running for GRACE + 3 s")
    assert get(d + ":OutputIntlk") == 1
    assert sim_signal(d, "output") == 1.0
    assert sim_signal(d, "vset") == pytest.approx(3000, abs=1)
    assert sim_log_lines(CMD % ("mat_co", 4)) == []  # no set or switching command ...
    assert len(sim_log_lines(r"mat_co INFO unit 4: CH1 FFFF")) == 1   # ... only the limit
    assert get(d + ":voltage:setpoint") == pytest.approx(3000, abs=1)  # taken over
    assert get(d + ":current:limit") == pytest.approx(7.5)           # from the defaults file
    assert sevr(d + ":voltage:setpoint") == 0 and get(d + ":voltage:setpoint.SIMM") == 0


def test_supply_switched_on_after_the_ioc_start():
    """The puller (unit 2) answers only 25 s after the simulator started: it is taken over then,
    and its limit from the defaults file (6 mA) is applied, with nothing left INVALID."""
    d = "AU-20P7-2"
    if sim_signal(d, "iset") != pytest.approx(0.006):
        assert sevr(d + ":voltage:read") == 3
        assert get(d + ":current:limit.STAT") == 17                 # restored, not yet applied
        assert get(d + ":current:limit") == pytest.approx(6.0)
    wait_for(lambda: all_valid(d, SUFFIXES + INTERNAL), 40,
             lambda: "puller taken over after it came on: %s" % not_valid(d, SUFFIXES + INTERNAL))
    assert sim_signal(d, "iset") == pytest.approx(0.006, rel=1e-4)
    assert get(d + ":current:get") == pytest.approx(6.0, abs=1e-3)
    assert get(d + ":SetToggleOutput") == 0
    assert sim_log_lines(CMD % ("mat_opt", 2)) == []


def test_every_pv_is_valid():
    """Normal operation: every PV of every polled supply has no alarm, also the internal records.
    The unpolled unit: set points, limit, echoes, SW setting and output PVs valid (read at the
    first contact); monitors and status were never read (INVALID, UDF)."""
    for d in POLLED:
        wait_for(lambda: all_valid(d, SUFFIXES + INTERNAL), 12,
                 lambda: "%s: alarm in %s" % (d, not_valid(d, SUFFIXES + INTERNAL)))
        wait_for(lambda: get(d + ":OutputIntlk.STAT") == 0, GRACE + 1, "OutputIntlk enabled")
    assert all_valid(UNPOLLED, WRITES + INTERNAL + ["voltage:get", "current:get",
                                                    "read_output_status"])
    for s in UNPOLLED_UNREAD:
        assert sevr("%s:%s" % (UNPOLLED, s)) == 3 and get("%s:%s.STAT" % (UNPOLLED, s)) == 17, s
    for pv in ("AU:alloff:set", "AU:alloff:chain1", "AU:alloff:chain2"):   # never used yet
        assert sevr(pv) == 0, pv


def test_unpolled_supply_makes_no_traffic():
    with control("mat_co") as c:
        c.stats(reset=True)
        time.sleep(3)
        assert c.stats()["per_unit"].get("6", {"requests": 0})["requests"] == 0


def test_units_and_alias():
    for d in AU:
        assert get(d + ":current:read.EGU") == "mA"
    for d in ("REK-1", "REK-2"):
        for s in ("current:limit", "current:get", "current:read"):
            assert get("%s:%s.EGU" % (d, s)) == "A"
    assert get("AU-20P7-3:current:limit.DRVH") == 7.5
    assert get("AU-20P7-1:current:limit.DRVH") == 15
    assert get("AU-20P7-3:voltage:setpoint.DRVH") == 20000
    assert get("REK-2:current:limit.DRVH") == 55
    # the lab's name is the same record
    put("AU-20P7-3:current:setpoint", 5.0)
    assert get("AU-20P7-3:current:limit") == pytest.approx(5.0)
    assert get("AU-20P7-3:current:setpoint.NAME") == "AU-20P7-3:current:limit"


@pytest.mark.parametrize("d", list(POLLED))
def test_set_points_echo_and_monitors(d):
    _, unit, vfs, ifs, load, to_a = POLLED[d]
    if get(d + ":SetToggleOutput") == 1:
        switch(d, False)
    put(d + ":current:limit", 0.8 * ifs)
    wait_for(lambda: get(d + ":current:get") == pytest.approx(0.8 * ifs, rel=1e-4), ECHO,
             "%s: current echo" % d)
    assert sim_signal(d, "iset", "target") == pytest.approx(0.8 * ifs * to_a, rel=1e-4)
    switch(d, True)
    # switching does not touch the limit (no ICN any more)
    wait_for(lambda: get(d + ":read_output_status") == 1, ECHO, "SW setting on")
    assert get(d + ":current:get") == pytest.approx(0.8 * ifs, rel=1e-4)
    put(d + ":voltage:setpoint", 0.5 * vfs)
    wait_for(lambda: get(d + ":voltage:get") == pytest.approx(0.5 * vfs, abs=vfs / 65535), ECHO,
             "%s: voltage echo" % d)
    assert sevr(d + ":voltage:setpoint") == 0 and sevr(d + ":current:limit") == 0
    amps = 0.5 * vfs / load / to_a
    wait_for(lambda: get(d + ":voltage:read") == pytest.approx(0.5 * vfs, abs=0.002 * vfs), 3,
             "%s: voltage:read follows" % d)
    wait_for(lambda: get(d + ":current:read") == pytest.approx(amps, abs=0.002 * ifs), 3,
             "%s: current:read = V / load" % d)
    watts = 0.5 * vfs * amps * to_a
    assert get(d + ":power:read") == pytest.approx(watts, rel=0.015)
    switch(d, False)
    wait_for(lambda: get(d + ":voltage:read") < 0.002 * vfs, 3, "%s: output falls to 0" % d)
    assert get(d + ":current:get") == pytest.approx(0.8 * ifs, rel=1e-4)   # limit kept


def test_current_limit_pulls_the_voltage_down():
    d = "AU-20P7-3"
    switch(d, True)
    put(d + ":voltage:setpoint", 16000)              # 4 mA into 4 MOhm ...
    put(d + ":current:limit", 1.0)                   # ... limited to 1 mA: 4 kV
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


def test_permit_latches():
    """Permit lost (open, INVALID): output off and request cleared; permit back: stays off."""
    for d in ("AU-20P7-3", "REK-1"):
        switch(d, True)
        put("interlock_open", 1)                     # permit open: forced off, request cleared
        wait_for(lambda: get(d + ":status:read") == 0, 3, "%s off by the permit" % d)
        assert get(d + ":ToggleOutput") == 0 and get(d + ":SetToggleOutput") == 0
        put(d + ":SetToggleOutput", 1)               # a request while the permit is open ...
        wait_for(lambda: get(d + ":SetToggleOutput") == 0, 2, "... is cleared at once")
        put("interlock_open", 0)                     # permit back: nothing switches on
        time.sleep(2)
        assert get(d + ":status:read") == 0 and sim_signal(d, "output") == 0
        switch(d, True)                              # the operator switches on again
        put("interlock_open.ZSV", "INVALID")         # permit INVALID with value 0: open
        put("interlock_open", 0)
        try:
            wait_for(lambda: get(d + ":status:read") == 0, 3, "%s off, permit INVALID" % d)
            assert sevr(d + ":OutputIntlk") == 3 and get(d + ":SetToggleOutput") == 0
        finally:
            put("interlock_open.ZSV", "NO_ALARM")
            put("interlock_open", 0)
        time.sleep(2)
        assert get(d + ":status:read") == 0
        wait_for(lambda: sevr(d + ":OutputIntlk") == 0, 3, "permit valid again")


def test_disconnected_permit_counts_as_open():
    d = "REK-9"                                      # PERMIT=no:such:permit
    put(d + ":SetToggleOutput", 1)
    wait_for(lambda: get(d + ":SetToggleOutput") == 0, 3, "request cleared")
    assert get(d + ":OutputIntlk") == 0 and sevr(d + ":OutputIntlk") == 3
    with control("rek55") as c:
        assert c.get("9.output")["value"] == 0.0


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


def test_local_control_after_a_status_poll():
    """The front panel takes local control: status:read shows it, the status polls do not take
    it back (no REN), sets are not executed; switching from the control system takes it back."""
    d = "AU-20P7-3"
    switch(d, True)
    with control(d) as c:
        c.set("3.remote", 0)
        c.release("3.remote")
    wait_for(lambda: get(d + ":status:read") == 3, 3, "ON, LOCAL")
    assert sevr(d + ":status:read") == 1             # MINOR
    time.sleep(3)                                    # three status polls later: still local
    assert get(d + ":status:read") == 3 and sim_signal(d, "remote") == 0
    put(d + ":voltage:setpoint", 7000)               # not executed: CALC alarm
    assert sevr(d + ":voltage:setpoint") == 3
    switch(d, False)                                 # switching sends REN
    assert get(d + ":status:read") == 0 and sim_signal(d, "remote") == 1
    put(d + ":voltage:setpoint", 5000)
    assert sevr(d + ":voltage:setpoint") == 0


def test_silent_unit_does_not_stall_its_chain():
    d, other = "AU-20P7-4", "AU-20P7-3"
    switch(other, True)
    put(other + ":voltage:setpoint", 8000)
    with control(d) as c:
        c.fault("silent", unit=4)
        try:
            t0 = time.monotonic()
            fast = wait_for(lambda: invalid(d, ["voltage:read", "current:read", "power:read",
                                                "status:read"]), 3, "monitors and status INVALID")
            wait_for(lambda: invalid(d, ["voltage:get", "current:get", "read_output_status"]), 6,
                     "echoes INVALID")
            slow = time.monotonic() - t0
            put(d + ":voltage:setpoint", 3000)       # a set to a silent supply: INVALID
            assert sevr(d + ":voltage:setpoint") == 3
            rate = monitor_rate(other + ":voltage:read", 5.0)
            print("silent unit 4: monitors INVALID after %.1f s, echoes after %.1f s; unit 3 "
                  "keeps %.1f updates/s" % (fast, slow, rate))
            assert rate > 1.0                        # even share with the timeouts
            assert all_valid(other, ["voltage:read", "current:read", "status:read"])
        finally:
            c.clear("silent")
    wait_for(lambda: all_valid(d, [s for s in SUFFIXES if s != "voltage:setpoint"]), 12,
             "unit 4 recovers without an IOC restart")
    put(d + ":voltage:setpoint", 3000)
    assert sevr(d + ":voltage:setpoint") == 0
    switch(other, False)


def test_closed_chain_recovers():
    with control("mat_co") as c:
        c.fault("close")
        try:
            for d in ("AU-20P7-3", "AU-20P7-4"):
                wait_for(lambda: invalid(d, ["voltage:read", "status:read"]), 5, "%s INVALID" % d)
            # the internal polling records do not turn INVALID on a closed port
            for _ in range(20):
                assert sevr("AU-20P7-3:_poll:gate") == 0 and sevr("AU-20P7-3:_poll:tick") == 0
                time.sleep(0.1)
        finally:
            c.clear("close")
    for d in ("AU-20P7-3", "AU-20P7-4"):
        wait_for(lambda: all_valid(d), 20, "%s recovers after the chain is back" % d)


def test_limit_survives_an_ioc_restart():
    d = "AU-20P7-1"
    put(d + ":current:limit", 3.3)                   # saved by autosave within 5 s
    time.sleep(7)
    mark = sim_log_mark()
    restart_ioc()
    wait_for(lambda: all_valid(d, SUFFIXES + INTERNAL), 20, "%s valid after the restart" % d)
    assert get(d + ":current:limit") == pytest.approx(3.3)
    code = "%04X" % round(3.3 / 15 * 0xFFFF)
    assert sim_log_since(mark, r"mat_opt INFO unit 1: CH1 %s" % code)   # applied at the start
    assert sim_log_since(mark, CMD % ("mat_opt", 1)) == []              # nothing else sent


def test_ioc_start_while_a_chain_is_down():
    """The IOC starts while mat_co cannot be reached. When it can, everything comes up by
    itself: nothing INVALID left over, only REN and the limit sent."""
    with control("mat_co") as c:
        c.fault("close")
        try:
            restart_ioc()
            time.sleep(GRACE + 2)
            for d in ("AU-20P7-3", "AU-20P7-4"):
                assert invalid(d, ["voltage:read", "status:read"])
                assert sevr(d + ":output:init") == 0         # waits, no alarm of its own
            mark = sim_log_mark()
        finally:
            c.clear("close")
    for d in ("AU-20P7-3", "AU-20P7-4"):
        wait_for(lambda: all_valid(d, SUFFIXES + INTERNAL), 25, "%s comes up by itself" % d)
        unit = POLLED[d][1]
        assert sim_log_since(mark, CMD % ("mat_co", unit)) == []
    assert get("AU-20P7-4:SetToggleOutput") == sim_signal("AU-20P7-4", "sw")


def test_all_off():
    for d in AU:                                     # after the restarts: past GRACE
        wait_for(lambda: get(d + ":OutputIntlk.STAT") == 0, 15, "%s: OutputIntlk enabled" % d)
    for d in AU:
        if get(d + ":SetToggleOutput") == 0:
            switch(d, True)
    t0 = time.monotonic()
    put("AU:alloff:set", 1)
    wait_for(lambda: all(sim_signal(d, "output") == 0 for d in AU), 3, "every AU output off")
    took = time.monotonic() - t0
    for d in AU:
        for s in ("SetToggleOutput", "ToggleOutput", "read_output_status", "status:read"):
            wait_for(lambda: get("%s:%s" % (d, s)) == 0, ECHO, "%s:%s == 0" % (d, s))
    print("AU:alloff:set: every output off %.0f ms after the caput" % (took * 1000))
    wait_for(lambda: get("AU:alloff:set") == 0, 3, "AU:alloff:set back to 0")
    switch("AU-20P7-3", True)                        # one write switches a supply on again
    assert sim_signal("AU-20P7-2", "output") == 0
    switch("AU-20P7-3", False)
    for d in AU:
        assert sevr(d + ":ToggleOutput") == 0


def test_rek_full_scale_24_and_55_A():
    put("REK-1:current:limit", 12)
    put("REK-2:current:limit", 27.5)
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
