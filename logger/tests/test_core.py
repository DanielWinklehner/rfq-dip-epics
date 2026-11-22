"""The logger's rules without Channel Access and without a database (mist2log/core.py)."""
import math

import pytest

from mist2log import core
from mist2log.core import INVALID, MAJOR, NO_ALARM, Channel, Interval, Recorder

T0 = 1_800_000_000.0      # a whole minute (2027-01-15 08:00:00 UTC)


def recorder(*channels, **kw):
    return Recorder(list(channels), **kw)


def closed(rows, t):
    return [r for r in rows if r[1] == t]


# --- R3: intervals -------------------------------------------------------------------------------
def test_a_value_that_holds_is_stored_once_and_reads_as_the_end_state():
    out = []
    agg = Interval(1)
    agg.change(T0 + 0.5, 2.0, NO_ALARM, 1, out)
    for t in range(2, 3601):                   # a tick every second, as the logger does
        agg.advance(T0 + t, 1, out)
    assert len(out) == 1                       # only the interval with the change
    pv, t, mean, mn, mx, valid, sev, last, last_sev = out[0]
    assert (t, mean, mn, mx, valid, last, last_sev) == (T0, 2.0, 2.0, 2.0, 0.5, 2.0, NO_ALARM)
    assert sev == INVALID                      # the first half had no value (before the first update)


def test_mean_is_weighted_by_time_across_a_change():
    out = []
    agg = Interval(1)
    agg.change(T0 - 5, 1.0, NO_ALARM, 1, out)
    agg.change(T0 + 0.25, 5.0, NO_ALARM, 1, out)     # 1 for 0.25 s, then 5 for 0.75 s
    agg.advance(T0 + 1, 1, out)
    row = closed(out, T0)[0]
    assert row[2] == pytest.approx(1 * 0.25 + 5 * 0.75)
    assert (row[3], row[4], row[5]) == (1.0, 5.0, 1.0)


def test_an_interval_without_a_valid_value_is_a_gap_not_a_held_value():
    out = []
    agg = Interval(60)
    agg.change(T0 + 10, 3.0, NO_ALARM, 1, out)
    agg.change(T0 + 70, None, INVALID, 1, out)        # INVALID from 70 s on
    agg.advance(T0 + 240, 1, out)
    first, second = closed(out, T0)[0], closed(out, T0 + 60)[0]
    assert first[2] == 3.0 and first[7] == 3.0
    assert second[5] == pytest.approx(10 / 60) and second[7] is None and second[8] == INVALID
    assert second[6] == INVALID                       # worst severity
    assert not closed(out, T0 + 120)                  # the gap holds: read as the end state (none)


def test_worst_severity_of_the_interval():
    out = []
    agg = Interval(1)
    agg.change(T0, 1.0, NO_ALARM, 1, out)
    agg.change(T0 + 0.2, 1.5, MAJOR, 1, out)
    agg.change(T0 + 0.4, 1.0, NO_ALARM, 1, out)
    agg.advance(T0 + 1, 1, out)
    assert closed(out, T0)[0][6] == MAJOR and closed(out, T0)[0][8] == NO_ALARM


# --- R2, R4: rows and events --------------------------------------------------------------------
def test_written_pv_gives_a_change_row_and_a_set_event_with_old_and_new():
    ch = Channel(1, "X:set", "events", "number", written=True)
    rec = recorder(ch)
    rec.update(ch, 1.0, None, NO_ALARM, 0, T0, T0)
    rec.update(ch, 2.5, None, NO_ALARM, 0, T0 + 1, T0 + 1)
    b = rec.tick(T0 + 2)
    assert [r[2] for r in b.changes] == [1.0, 2.5]
    sets = [e for e in b.events if e[2] == "set"]
    assert [(e[3], e[4]) for e in sets] == [(None, "1"), ("1", "2.5")]


def test_alarm_events_and_disconnect_gap():
    ch = Channel(1, "X:read", "raw", "number")
    rec = recorder(ch)
    rec.update(ch, 1.0, None, NO_ALARM, 0, T0, T0)
    rec.update(ch, 1.0, None, INVALID, 9, T0 + 1, T0 + 1)
    rec.disconnect(ch, T0 + 2)
    rec.update(ch, 1.0, None, NO_ALARM, 0, T0 + 3, T0 + 3)
    b = rec.tick(T0 + 10)
    assert [(e[3], e[4]) for e in b.events if e[2] == "alarm"] == [("NO_ALARM", "INVALID"), ("INVALID", "NO_ALARM")]
    assert [(e[3], e[4]) for e in b.events if e[2] == "connection"] == [("connected", "lost"), ("lost", "back")]
    assert [r[4] for r in b.raw] == [NO_ALARM, INVALID, None, NO_ALARM]       # severity None: the gap
    assert closed(b.seconds, T0 + 1)[0][2] is None and closed(b.seconds, T0 + 1)[0][7] is None   # INVALID: no value
    assert closed(b.seconds, T0 + 2)[0][7] is None                              # no value at its end


def test_enumeration_keeps_number_and_word_and_loop_mode_carries_its_reason():
    reason = Channel(2, "L:reason:get", "events", "enum", states=["none", "interlock open"])
    mode = Channel(1, "L:mode:get", "events", "enum", states=["MANUAL", "PID"], context=2)
    rec = recorder(mode, reason)
    rec.update(reason, 1, "interlock open", NO_ALARM, 0, T0, T0)
    rec.update(mode, 0, "MANUAL", NO_ALARM, 0, T0, T0)
    b = rec.tick(T0 + 1)
    row = b.changes[-1]
    assert (row[2], row[3]) == (0, "MANUAL")
    event = [e for e in b.events if e[1] == 1][0]
    assert event[4] == "MANUAL (0)" and event[8] == "L:reason:get: interlock open (1)"


def test_text_pv_is_stored_as_text_without_intervals():
    ch = Channel(1, "IOC:mode", "events", "text")
    rec = recorder(ch)
    rec.update(ch, None, "sim", NO_ALARM, 0, T0, T0)
    b = rec.tick(T0 + 120)
    assert b.changes[0][2:4] == (None, "sim") and not b.seconds and not ch.aggs


# --- R7: time stamps ------------------------------------------------------------------------------
def test_never_processed_record_is_stored_under_the_loggers_time():
    ch = Channel(1, "X:set", "events", "number", written=True)
    rec = recorder(ch)
    rec.update(ch, 0.0, None, INVALID, 17, 631152000.0, T0)        # 1990-01-01, UDF
    row = rec.tick(T0 + 1).changes[0]
    assert row[1] == T0 and row[6] == core.FLAG_UDF_TIME


def test_time_stamp_far_off_is_replaced_flagged_and_logged_once():
    ch = Channel(1, "X:read", "raw", "number")
    rec = recorder(ch, clock_skew=10.0)
    rec.update(ch, 1.0, None, NO_ALARM, 0, T0, T0)
    rec.update(ch, 2.0, None, NO_ALARM, 0, T0 + 1 + 3600, T0 + 1)    # an IOC an hour ahead
    rec.update(ch, 3.0, None, NO_ALARM, 0, T0 + 2 - 3600, T0 + 2)    # an hour behind
    b = rec.tick(T0 + 3)
    assert [(r[1], r[6]) for r in b.raw] == [(T0, 0), (T0 + 1, core.FLAG_CLOCK), (T0 + 2, core.FLAG_CLOCK)]
    assert len([e for e in b.events if e[4] == "clocks apart"]) == 1


def test_old_time_stamp_of_the_first_value_is_kept_unless_it_lies_before_a_gap():
    a = Channel(1, "A", "raw", "number")
    b = Channel(2, "B", "raw", "number")
    rec = recorder(a, b)
    rec.start((T0, T0, T0), {}, T0 + 100)                          # the last run ended at T0
    rec.update(a, 1.0, None, NO_ALARM, 0, T0 + 50, T0 + 100)       # processed while the logger was down
    rec.update(b, 1.0, None, NO_ALARM, 0, T0 - 50, T0 + 100)       # processed before: stored when seen
    batch = rec.tick(T0 + 101)
    assert [(r[0], r[1], r[6]) for r in batch.raw if r[4] is not None] == [(1, T0 + 50, 0), (2, T0 + 100, core.FLAG_RESUMED)]
    assert sorted((r[0], r[1]) for r in batch.raw if r[4] is None) == [(1, T0), (2, T0)]     # gap rows at the end of the last run


# --- R6: lost rows --------------------------------------------------------------------------------
def test_resume_after_lost_rows_writes_a_gap_and_the_present_state():
    ch = Channel(1, "X", "raw", "number")
    rec = recorder(ch)
    rec.update(ch, 4.0, None, NO_ALARM, 0, T0, T0)
    rec.tick(T0 + 62)                          # ticks go on while the rows are lost
    b = rec.resume((T0 + 1, T0, T0), T0 + 60)
    assert [(r[1], r[2], r[6]) for r in b.raw] == [(T0 + 1, None, core.FLAG_LOGGER), (T0 + 60, 4.0, core.FLAG_RESUMED)]
    assert all(agg.dirty for agg in ch.aggs.values())
    later = rec.tick(T0 + 70)
    assert closed(later.seconds, T0 + 60) and closed(later.seconds, T0 + 60)[0][2] == 4.0


def test_store_drops_batches_that_do_not_fit_and_reports_the_loss_once(monkeypatch):
    from mist2log import store

    class S:
        db = {}
        reader_password = ""
        buffer_rows = 3
    s = store.Store(S(), {})
    s.db_ok = True
    full = core.Batch(T0)
    full.raw = [(1, T0, 1.0, None, 0, 0, 0)] * 3
    full.through = (T0, T0, T0)
    late = core.Batch(T0 + 1)
    late.raw = [(1, T0 + 1, 1.0, None, 0, 0, 0)] * 2
    s.put(full)
    s.put(late)
    assert (s.buffered, s.dropped) == (3, 2)
    assert s.take_loss() is None               # still rows waiting
    s.queue.clear()
    s.buffered = 0
    assert s.take_loss() == [(T0, T0, T0), T0 + 1, 2]
    assert s.take_loss() is None and not math.isnan(s.status()["buffer"])


# --- a loop's actuator ------------------------------------------------------------------------------
def loop_channels():
    mode = Channel(1, "L:mode:get", "events", "enum", states=["MANUAL", "PID"], context=2)
    reason = Channel(2, "L:reason:get", "events", "enum", states=["none", "interlock open"])
    act = Channel(3, "S:current:setpoint", "events", "number", written=True, driver=(1, 1))
    return mode, reason, act


def test_writes_of_a_loop_in_pid_are_a_signal_and_set_commands_outside():
    mode, reason, act = loop_channels()
    rec = recorder(mode, reason, act)
    rec.update(mode, 0, "MANUAL", NO_ALARM, 0, T0, T0)
    rec.update(reason, 0, "none", NO_ALARM, 0, T0, T0)
    rec.update(act, 80.0, None, NO_ALARM, 0, T0, T0)
    rec.update(act, 81.0, None, NO_ALARM, 0, T0 + 1, T0 + 1)          # the operator: a set command
    rec.update(mode, 1, "PID", NO_ALARM, 0, T0 + 2, T0 + 2)           # the loop takes over
    for k in range(10):                                               # it writes five times a second
        rec.update(act, 81.2 + 0.2 * k, None, NO_ALARM, 0, T0 + 2.2 + 0.2 * k, T0 + 2.2 + 0.2 * k)
    rec.update(mode, 0, "MANUAL", NO_ALARM, 0, T0 + 4.5, T0 + 4.5)    # hand-back
    rec.update(act, 85.0, None, NO_ALARM, 0, T0 + 6, T0 + 6)          # the operator again
    b = rec.tick(T0 + 70)
    sets = [(e[3], e[4]) for e in b.events if e[1] == act.id and e[2] == "set"]
    assert sets == [(None, "80"), ("80", "81"), ("83", "85")]         # none of the loop's ten writes
    assert [r[2] for r in b.changes if r[0] == act.id] == [80.0, 81.0, 83.0, 85.0]   # 83: its value at the hand-back
    raw = [(r[1], r[2], r[6]) for r in b.raw if r[0] == act.id]
    assert raw[0] == (T0 + 2, 81.0, core.FLAG_DRIVEN) and raw[-1] == (T0 + 4.5, None, core.FLAG_DRIVEN)
    assert len(raw) == 12                                             # the value at the start, ten writes, the end
    secs = {r[1]: r for r in b.seconds if r[0] == act.id}
    assert set(secs) == {T0 + 2, T0 + 3, T0 + 4}                      # intervals only while in PID
    assert secs[T0 + 4][7] is None                                    # and nothing held after it


def test_a_mode_event_carries_the_reason_that_comes_after_it():
    # the loop's records are written in this order: request, mode, reason (LOOP.md, loop.db)
    mode, reason, act = loop_channels()
    rec = recorder(mode, reason, act)
    rec.update(reason, 0, "none", NO_ALARM, 0, T0, T0)
    rec.update(mode, 1, "PID", NO_ALARM, 0, T0, T0)
    rec.tick(T0 + 1)
    rec.update(mode, 0, "MANUAL", NO_ALARM, 0, T0 + 10, T0 + 10)
    b = rec.tick(T0 + 10.00003)                                       # a tick between mode and reason
    rec.update(reason, 1, "interlock open", NO_ALARM, 0, T0 + 10.00006, T0 + 10.00006)
    b2 = rec.tick(T0 + 11)
    events = [e for e in b.events + b2.events if e[1] == mode.id]
    assert [(e[4], e[8]) for e in events] == [("MANUAL (0)", "L:reason:get: interlock open (1)")]
    assert events[0][0] == T0 + 10                                    # at the time of the mode change


def test_a_mode_event_without_a_new_reason_takes_the_one_in_effect_after_the_wait():
    mode, reason, act = loop_channels()
    rec = recorder(mode, reason, act)
    rec.update(reason, 1, "interlock open", NO_ALARM, 0, T0, T0)
    rec.update(mode, 0, "MANUAL", NO_ALARM, 0, T0 + 1, T0 + 1)
    assert not [e for e in rec.tick(T0 + 1.2).events if e[1] == mode.id]       # still waiting
    events = [e for e in rec.tick(T0 + 1 + core.CONTEXT_WAIT).events if e[1] == mode.id]
    assert [e[8] for e in events] == ["L:reason:get: interlock open (1)"]
