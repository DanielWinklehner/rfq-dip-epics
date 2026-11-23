"""Off as a state (P45, task T20): while the permit is lost and a supply reports its output on by a
valid reading, _permit:enforce starts the off sequence of _out:switch again (REN, RST, SW0, SW?),
1 to 2 s after the IOC has the reading and then every 2 s, and counts the sequences in its value.

What the IOC writes to the line is read from the asyn trace (records DEVTEST:asyn:<port> of
ioc.cmd, switched on only while a test watches a supply): the simulator logs REN only when it
takes control back from the front panel. Runs after test_matsusada.py (file order), whose IOC
restarts it does not need.
"""
import contextlib
import os
import re
import time

import epics
import pytest

from mat import (BUILD, GRACE, POLLED, control, get, invalid, put, restart_ioc, sevr,
                 sim_log_mark, sim_log_since, sim_signal, switch, wait_for)

SUPPLIES = ["AU-20P7-3", "REK-1"]            # one AU unit and one REK unit
UNPOLLED = "AU-20P7-6"                       # SCAN_MON, SCAN_GET, SCAN_STS Passive
PORT = {"AU-20P7-3": ("mat_co", 5002), "AU-20P7-6": ("mat_co", 5002), "REK-1": ("REK", 5003)}
CHAIN = {"AU-20P7-3": "mat_co", "AU-20P7-6": "mat_co", "REK-1": "rek"}
UNIT = {"AU-20P7-3": 3, "AU-20P7-6": 6, "REK-1": 1}

# The off sequence, 1 to 2 s after the reading (two evaluations of a 1 s scan), then the sequence
# itself (four commands, about 0.1 s) and the read-back of SW? (FLNK of ToggleOutput).
STS_POLL = 1.0                               # SCAN_STS
EVALUATIONS = 2.0                            # two evaluations of the 1 s scan
OFF_LIMIT = 4.0                              # off again within 4 s of the direct write
SEQUENCE = 0.5                               # REN, RST, SW0, SW? and its read-back, with margin
SWITCHING = re.compile(r"^(REN|RST|SW[01]|CH0 |CH1 |GTL)")   # commands, not queries


def count(d):
    return get(d + ":_permit:enforce")


def lose_permit():
    put("interlock_open", 1)
    for d in POLLED:
        wait_for(lambda: get(d + ":SetToggleOutput") == 0, 3, "%s: request cleared" % d)


def unit_log(d, mark):
    """The simulator's log lines of the unit since mark, without the prefix."""
    chain, unit = CHAIN[d], UNIT[d]
    time.sleep(1.0)                          # the harness writes the simulator log with a delay
    return [l.split("unit %d: " % unit)[1]
            for l in sim_log_since(mark, r"%s INFO unit %d: " % (chain, unit))]


def ioc_log_mark():
    with open(os.path.join(BUILD, "ioc.log")) as f:
        return len(f.readlines())


@contextlib.contextmanager
def trace(d):
    """The asyn trace of what the IOC writes to the supply's line, while the block runs. Yields
    a function that returns the commands written to the unit since the block began (text, after
    the unit number), in order."""
    port, tcp = PORT[d]
    rec = "DEVTEST:asyn:" + port
    mark = ioc_log_mark()
    put(rec + ".TIOM", 2)                    # escaped text
    put(rec + ".TMSK", 9)                    # errors and the driver's I/O
    head = re.compile(r"^\S+ \S+ sim:%d write \d+$" % tcp)
    data = re.compile(r"^#%d (.*)\\r$" % UNIT[d])

    def written():
        time.sleep(1.0)                      # the IOC log is written with a delay as well
        with open(os.path.join(BUILD, "ioc.log")) as f:
            lines = [l.rstrip("\n") for l in f.readlines()[mark:]]
        out = []
        for a, b in zip(lines, lines[1:]):
            m = data.match(b)
            if head.match(a) and m:
                out.append(m.group(1))
        return out

    try:
        yield written
    finally:
        put(rec + ".TMSK", 1)
        put(rec + ".TIOM", 0)


def commands(sent):
    """Switching commands among the written lines (no polls, no read-backs)."""
    return [c for c in sent if SWITCHING.match(c)]


def off_in_sim(d):
    return sim_signal(d, "output") == 0 and sim_signal(d, "sw") == 0


def gates_enabled():
    for d in POLLED:
        wait_for(lambda: get(d + ":OutputIntlk.DISA") == 0, 30, "%s: gate enabled" % d)


@pytest.fixture(autouse=True)
def enabled():
    gates_enabled()
    yield


def taken_over(d):
    """The unit that is not polled probes only once, at PINI: after an IOC start while its chain
    was closed (test_matsusada.py) it has had no first contact, so its gate is disabled and the
    rule rightly does nothing. Restart the IOC then (its chain is reachable now)."""
    if get(d + ":OutputIntlk.DISA") == 1:
        restart_ioc()
        wait_for(lambda: get(d + ":OutputIntlk.DISA") == 0, GRACE + 10, "%s: gate enabled" % d)
        gates_enabled()


def switch_off_directly(d):
    """Back to off after a test that switched on without a request (the request is 0, so writing
    it does not reach the gate): ToggleOutput 0, as a client would."""
    if sim_signal(d, "sw") != 0:
        put(d + ":ToggleOutput", 0)
        wait_for(lambda: off_in_sim(d), 3, "%s off" % d)


# --- 1. the state the fault leaves: permit lost, request off, the output on -----------------------

@pytest.mark.parametrize("d", SUPPLIES + [UNPOLLED])
def test_direct_write_while_the_permit_is_lost_is_switched_off(d):
    """A client writes ToggleOutput 1 while the permit is lost (P28; the same state as an off
    command of the gate that was lost, P45). The supply goes on and within 4 s it is off again:
    REN, RST, SW0 after the SW1, ToggleOutput and the request 0, the count up by one. Also for
    the unit that is not polled: its SW? is read after every switching (FLNK of ToggleOutput),
    its status never (INVALID, UDF), so the rule sees the read-back of the direct write."""
    if d == UNPOLLED:
        taken_over(d)
    lose_permit()
    n0 = count(d)
    mark = sim_log_mark()
    with trace(d) as written:
        put(d + ":ToggleOutput", 1)
        wait_for(lambda: sim_signal(d, "output") == 1, 2, "%s on by the direct write" % d)
        t_on = time.monotonic()
        wait_for(lambda: off_in_sim(d), OFF_LIMIT, "%s off again within %g s" % (d, OFF_LIMIT))
        took = time.monotonic() - t_on
        wait_for(lambda: get(d + ":read_output_status") == 0 and get(d + ":ToggleOutput") == 0,
                 3, "%s: SW? read back OFF, ToggleOutput 0" % d)
        sent = commands(written())
    assert sent == ["RST", "SW1", "REN", "RST", "SW0"], sent
    assert unit_log(d, mark) == ["RST", "SW1", "RST", "SW0"]
    assert get(d + ":SetToggleOutput") == 0
    assert count(d) == n0 + 1
    if d == UNPOLLED:
        assert sevr(d + ":status:read") == 3 and get(d + ":status:read.STAT") == 17   # never read
    print("%s: on by a direct write, off again after %.2f s" % (d, took))


# --- 2. the front panel while the permit is lost ------------------------------------------------

@pytest.mark.parametrize("d", SUPPLIES)
def test_front_panel_switch_on_while_the_permit_is_lost(d):
    """Permit lost, then the front panel takes local control and switches on. The first off
    sequence (REN first, which takes control back) goes out within one status poll, two
    evaluations and the sequence. The simulator does not keep a SW setting made outside the line
    after its release (it goes back to the last commanded one), so the test holds sw at 1 until
    the IOC's SW0 has arrived and then releases it: the output follows that SW0. The read-back of
    SW? during the hold read 1, so one more sequence may follow (count up by 1 or 2); then the
    sending stops."""
    unit = UNIT[d]
    lose_permit()
    n0 = count(d)
    mark = sim_log_mark()
    with control(d) as c:
        c.set("%d.remote" % unit, 0)         # the front panel takes control and keeps it
        c.release("%d.remote" % unit)
        c.set("%d.sw" % unit, 1)             # and switches on
        t0 = time.monotonic()
        try:
            wait_for(lambda: get(d + ":status:read") == 3, STS_POLL + 0.5, "%s: ON, LOCAL" % d)
            limit = STS_POLL + EVALUATIONS + SEQUENCE
            wait_for(lambda: count(d) > n0 and sim_signal(d, "remote") == 1, limit,
                     "%s: the off sequence (REN first) within %g s of the switch-on" % (d, limit))
            time.sleep(0.3)                  # RST, SW0 and the read-back behind the REN
            took = time.monotonic() - t0
        finally:
            c.release("%d.sw" % unit)
    wait_for(lambda: off_in_sim(d) and sim_signal(d, "remote") == 1, 1, "%s off, remote" % d)
    wait_for(lambda: get(d + ":status:read") == 0, STS_POLL + 0.5, "%s: OFF (remote)" % d)
    log = unit_log(d, mark)
    assert log[:4] == ["front panel: local", "REN (remote control on)", "RST", "SW0"], log
    wait_for(lambda: get(d + ":read_output_status") == 0, 6, "%s: SW? read back OFF" % d)
    n1 = count(d)
    assert n1 - n0 in (1, 2), (n0, n1)
    time.sleep(2 * EVALUATIONS + 1)          # the sending stops
    assert count(d) == n1
    print("%s: front panel on while the permit is lost: REN, SW0 after %.2f s (limit %g s), "
          "%d sequences" % (d, took, limit, n1 - n0))


# --- 3. permit present: nothing changes -----------------------------------------------------------

@pytest.mark.parametrize("d", SUPPLIES)
def test_with_the_permit_a_direct_write_and_the_front_panel_stay_on(d):
    """With the permit present a direct write of ToggleOutput (P28) and a supply in local control
    with its output on stay on for 5 s, nothing is sent to them, and the count does not move."""
    unit = UNIT[d]
    n0 = count(d)
    mark = sim_log_mark()
    try:
        put(d + ":ToggleOutput", 1)
        wait_for(lambda: sim_signal(d, "output") == 1, 2, "%s on by the direct write" % d)
        for _ in range(10):
            time.sleep(0.5)
            assert sim_signal(d, "output") == 1, "%s switched off" % d
        with control(d) as c:                # the front panel takes control, the output on
            c.set("%d.remote" % unit, 0)
            c.release("%d.remote" % unit)
        wait_for(lambda: get(d + ":status:read") == 3, STS_POLL + 0.5, "%s: ON, LOCAL" % d)
        for _ in range(10):
            time.sleep(0.5)
            assert sim_signal(d, "output") == 1 and sim_signal(d, "remote") == 0, d
        assert count(d) == n0
        assert unit_log(d, mark) == ["RST", "SW1", "front panel: local"]
    finally:
        with control(d) as c:
            c.set("%d.remote" % unit, 1)
            c.release("%d.remote" % unit)
        switch_off_directly(d)


# --- 4. a normal permit loss sends one off sequence --------------------------------------------

ROUNDS = 20       # the test that the rule (without an activity input of the periodic read of
                  # SW?) sends nothing more at a normal permit loss. x 6 supplies = 120 permit losses: a doubled sequence in 3 % of them is missed
                  # with a probability of 0.97^120 = 2.6 %, in 5 % of them with 0.2 %
SETTLE = 3.0      # s after the output went off: a second sequence would start within two
                  # evaluations (2 s) after the readings, plus margin


def test_a_normal_permit_loss_sends_exactly_one_off_sequence(capsys):
    """Every polled supply on, the permit lost: each supply receives SW0 exactly once and the
    count does not move. Repeated ROUNDS times."""
    supplies = list(POLLED)
    n0 = {d: count(d) for d in supplies}
    mark = sim_log_mark()
    for _ in range(ROUNDS):
        for d in supplies:
            put(d + ":SetToggleOutput", 1)
        for d in supplies:
            wait_for(lambda: sim_signal(d, "output") == 1 and get(d + ":read_output_status") == 1
                     and get(d + ":status:read") == 1, 3, "%s on" % d)
        time.sleep(0.2 + 0.8 * (time.monotonic() % 1))     # vary the phase against the scans
        put("interlock_open", 1)
        for d in supplies:
            wait_for(lambda: off_in_sim(d), 3, "%s off by the permit" % d)
        time.sleep(SETTLE)
        assert {d: count(d) for d in supplies} == n0
        put("interlock_open", 0)
        for d in supplies:
            wait_for(lambda: get(d + ":OutputIntlk.A") == 0, 3, "%s: permit back" % d)
    time.sleep(1.0)
    for d in supplies:
        chain, unit = POLLED[d][:2]
        lines = sim_log_since(mark, r"%s INFO unit %d: SW[01]$" % (chain, unit))
        sw0 = [l for l in lines if l.endswith("SW0")]
        sw1 = [l for l in lines if l.endswith("SW1")]
        assert (len(sw1), len(sw0)) == (ROUNDS, ROUNDS), (d, len(sw1), len(sw0))
    with capsys.disabled():
        print("\n%d permit losses (%d rounds x %d supplies): one SW0 each, counts unchanged"
              % (ROUNDS * len(supplies), ROUNDS, len(supplies)))


# --- 5. a supply that does not answer is not flooded ---------------------------------------------

@pytest.mark.parametrize("d", SUPPLIES)
def test_a_silent_supply_is_not_flooded(d):
    """The permit lost and a supply that keeps its output on (sw held at 1: it does not follow
    SW0): a sequence every 2 s. Then it stops answering: status:read turns INVALID at its next
    poll, read_output_status at its next read, which is at the latest the read-back of the next
    sequence, so at most one more goes out; then none. It answers again and still reports on:
    the sending starts again."""
    unit = UNIT[d]
    lose_permit()
    with control(d) as c:
        c.set("%d.sw" % unit, 1)
        try:
            n0 = count(d)
            wait_for(lambda: count(d) >= n0 + 2, 2 * EVALUATIONS + STS_POLL + 2,
                     "%s: a sequence every 2 s while it reports on" % d)
            c.fault("silent", unit=unit)
            n_silent = count(d)
            wait_for(lambda: invalid(d, ["status:read", "read_output_status"]), 8,
                     "%s: both readings INVALID" % d)
            n_invalid = count(d)
            assert n_invalid - n_silent <= 1, (n_silent, n_invalid)
            time.sleep(3 * EVALUATIONS)
            assert count(d) == n_invalid, "sent to a silent supply"
            c.clear("silent")
            t0 = time.monotonic()
            limit = STS_POLL + 0.2 + EVALUATIONS + 0.5
            wait_for(lambda: count(d) > n_invalid, limit, "%s: sending again after it answers" % d)
            print("%s: %d sequences after it fell silent, sending again %.1f s after it answered"
                  % (d, n_invalid - n_silent, time.monotonic() - t0))
        finally:
            c.clear("silent")
            c.release("%d.sw" % unit)
    wait_for(lambda: off_in_sim(d), OFF_LIMIT, "%s off" % d)


# --- 6. an IOC start with the supply on and the permit lost --------------------------------------

def test_ioc_start_with_an_output_on_and_the_permit_lost():
    """Both supplies on, the IOC restarted and the permit lost before the supplies' first
    contact: nothing is sent before GRACE is over, then one off sequence (the gate's: the output
    state taken over as on, the permit lost), and the count stays 0.
    The supplies do not answer until the permit has been written. GRACE counts from the first
    contact, so the test does not depend on how soon its Channel Access client finds the
    restarted IOC (seen once: later than GRACE, the gates were enabled before the permit could
    be written)."""
    for d in SUPPLIES:
        switch(d, True)
    mark = sim_log_mark()
    with contextlib.ExitStack() as stack:
        ctl = {d: stack.enter_context(control(d)) for d in SUPPLIES}
        try:
            for d in SUPPLIES:
                ctl[d].fault("silent", unit=UNIT[d])
            restart_ioc()
            put("interlock_open", 1)
            for d in SUPPLIES:
                assert get(d + ":_init:probe.DISA") == 0, "%s: first contact with a silent supply" % d
                assert get(d + ":OutputIntlk.DISA") == 1, "%s: the gate was enabled already" % d
        finally:
            for d in SUPPLIES:
                ctl[d].clear("silent", unit=UNIT[d])
    for d in SUPPLIES:
        wait_for(lambda: get(d + ":_init:probe.DISA") == 1, 4, "%s: first contact" % d)
        assert get(d + ":OutputIntlk.DISA") == 1, "%s: the gate enabled at the first contact" % d
    while any(get(d + ":OutputIntlk.DISA") == 1 for d in SUPPLIES):
        for d in SUPPLIES:
            if get(d + ":OutputIntlk.DISA") == 1:
                assert sim_signal(d, "output") == 1, "%s switched off before GRACE" % d
        time.sleep(0.05)
    for d in SUPPLIES:
        wait_for(lambda: off_in_sim(d), 2, "%s off after GRACE" % d)
    time.sleep(2 * EVALUATIONS + 1)
    for d in SUPPLIES:
        assert count(d) == 0, d
        log = [l for l in unit_log(d, mark) if SWITCHING.match(l) and not l.startswith("CH1 ")]
        assert log == ["RST", "SW0"], (d, log)   # REN is not logged in remote control; CH1:
                                                 # the limit, sent at the first contact
        assert get(d + ":SetToggleOutput") == 0


# --- 7, 8. the structure, read from the running IOC ----------------------------------------------

INPUTS = {"INPA": ":OutputIntlk.A", "INPB": ":OutputIntlk.C", "INPC": ":OutputIntlk.DISA",
          "INPD": ":read_output_status", "INPE": ":read_output_status.SEVR",
          "INPF": ":status:read", "INPG": ":status:read.SEVR", "INPH": ":_out:switch.PACT",
          "INPI": ":ToggleOutput.PACT"}


@pytest.mark.parametrize("d", list(POLLED) + [UNPOLLED, "REK-9"])
def test_structure_of_the_enforce_record(d):
    """_permit:enforce as its comment names it: a calcout scanned every 1 s, its inputs NPP
    database links to the named fields, no delay, On Change, output 6 to _out:switch.SELN PP; no
    alarm, its value the count. No .PACT input of a record that is scanned periodically."""
    r = d + ":_permit:enforce"
    f = lambda fld: epics.caget("%s.%s" % (r, fld), as_string=True, timeout=3, use_monitor=False)
    calc = epics.caget(r + ".CALC$", as_string=True, timeout=3, use_monitor=False)   # > 40 characters
    assert f("RTYP") == "calcout"
    assert f("SCAN") == "1 second"
    for fld, target in INPUTS.items():
        assert f(fld).split()[:2] == [d + target, "NPP"], (fld, f(fld))
    for fld in ("INPJ", "INPK", "INPL"):
        assert f(fld) == "", (fld, f(fld))
    assert calc == "K:=(A||B>=3)&&C=0&&!(H||I)&&(D=1&&E<3||(F=1||F=3)&&G<3)?K+1:0;L:=L+(K>=2);K:=K>=2?0:K;L"
    assert f("OOPT") == "On Change" and f("DOPT") == "Use OCAL"
    assert f("OCAL") == "6" and float(f("ODLY")) == 0.0
    assert f("OUT").split()[:2] == [d + ":_out:switch.SELN", "PP"], f("OUT")
    assert f("IVOA") == "Continue normally"
    # every activity input (.PACT) reads a record that is not scanned periodically: one scanned
    # in the same list would be busy at every evaluation and switch the rule off (SCAN_GET 1 s)
    for fld in ("INP" + c for c in "ABCDEFGHIJKL"):
        target = f(fld).split()[0] if f(fld) else ""
        if target.endswith(".PACT"):
            rec = target[:-len(".PACT")]
            scan = epics.caget(rec + ".SCAN", as_string=True, timeout=3, use_monitor=False)
            assert scan == "Passive", (fld, rec, scan)
    assert sevr(r) == 0
    assert get(r) == get(r + ".L")
