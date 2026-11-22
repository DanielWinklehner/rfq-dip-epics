"""What the logger makes of the monitor updates of its PVs: rows and events, without Channel Access
and without a database, so that every rule here is tested on its own (tests/test_core.py).

Times are POSIX seconds (float). A Batch holds the rows of one tick; store.py writes it.

Rows (docs/emulation/LOGGER.md, "Data model"):
  raw, changes  (pv, t, value, text, severity, status, flags): every update as the IOC sent it.
                A row with severity None is a gap: from its time on there is no value (the PV
                disconnected, or the logger knows nothing: it was not running, or rows were lost).
  seconds, minutes  (pv, t, mean, min, max, valid, severity, last, last_severity): one interval,
                weighted by time over the part with a valid value (severity below INVALID). Only
                intervals in which something happened are stored; an interval without a row
                reads as the end state (last, last_severity) of the row before it.
  events        (t, pv, kind, old, new, value, severity, status, detail)
"""
import math

NO_ALARM, MINOR, MAJOR, INVALID = 0, 1, 2, 3
SEVERITY = ["NO_ALARM", "MINOR", "MAJOR", "INVALID"]
STATUS = ["NO_ALARM", "READ", "WRITE", "HIHI", "HIGH", "LOLO", "LOW", "STATE", "COS", "COMM",
          "TIMEOUT", "HWLIMIT", "CALC", "SCAN", "LINK", "SOFT", "BAD_SUB", "UDF", "DISABLE",
          "SIMM", "READ_ACCESS", "WRITE_ACCESS"]

# flags of a raw or changes row
FLAG_CLOCK = 1      # the IOC's time stamp was far from the logger's clock: stored under the logger's time
FLAG_UDF_TIME = 2   # time stamp of 1990 (record never processed): stored under the logger's time
FLAG_RESUMED = 4    # first value after a gap whose time stamp lies before the gap: stored when seen
FLAG_LOGGER = 8     # gap written by the logger (it was not running, or rows were lost), not a disconnect
FLAG_DRIVEN = 16    # a loop took over (raw: the value then) or gave back (raw: gap, changes: the value then)

# A mode event waits this long for the reason that belongs to it (the loop's records are written
# in the order request, mode, reason), then takes the reason in effect.
CONTEXT_WAIT = 0.5

# A time stamp before 2000 is that of a record never processed (EPICS epoch, 1990-01-01).
NEVER_PROCESSED_BEFORE = 946684800.0


class Channel:
    """One logged PV: its settings from the registry and what the logger last knew of it."""

    def __init__(self, pv_id, name, tier, kind, written=False, states=None, context=None, driver=None):
        self.id, self.name, self.tier, self.kind = pv_id, name, tier, kind   # kind: number, enum, text
        self.written, self.states, self.context = written, states or [], context
        # driver: (id of a loop's mode PV, its value in PID) for a PV a loop writes. While the loop
        # is in PID the PV is a signal (raw, seconds, minutes), else an events PV.
        self.driver = driver
        self.driven = False
        self.connected = False
        self.seen = False          # a value arrived in this run
        self.value = self.text = None
        self.severity = self.status = None
        self.known_severity = None   # last severity written to the event log (also from the last run)
        self.known_text = None       # last value text of an events PV written to the event log
        self.t = -math.inf         # time of the last row
        self.gap_t = -math.inf     # time of the last gap: a value stamped before it is from before the gap
        self.clock_warned = False
        widths = {"raw": (1, 60), "seconds": (1, 60), "minutes": (60,)}.get(tier, (1, 60) if driver else ())
        self.aggs = {w: Interval(w) for w in widths} if kind != "text" else {}

    @property
    def table(self):
        return "raw" if self.driven else {"raw": "raw", "events": "changes"}.get(self.tier)

    @property
    def signal(self):
        """Its intervals are computed: a raw, seconds or minutes PV, or one a loop drives now."""
        return self.driver is None or self.driven


class Interval:
    """Mean, minimum, maximum and worst severity of one PV per interval of `width` seconds,
    weighted by time. The state (a valid value, or none) holds from one update to the next."""

    def __init__(self, width):
        self.w = width
        self.b = None            # start of the open interval
        self.t = None            # time up to which the open interval has taken the state
        self.v = None            # the state: a valid value, or None
        self.sev = INVALID       # its severity (not connected counts as INVALID)
        self.dirty = False
        self._reset()

    def _reset(self):
        self.sum = self.vt = 0.0
        self.mn = self.mx = self.worst = None

    def _take(self, until):
        d = until - self.t
        if d > 0:
            self.worst = self.sev if self.worst is None else max(self.worst, self.sev)
            if self.v is not None:
                self.sum += self.v * d
                self.vt += d
                self.mn = self.v if self.mn is None else min(self.mn, self.v)
                self.mx = self.v if self.mx is None else max(self.mx, self.v)
            self.t = until

    def advance(self, t, pv, out):
        """Close every interval that ends at or before t; append the stored ones to out."""
        if self.b is None:
            return
        while t >= self.b + self.w:
            end = self.b + self.w
            self._take(end)
            if self.dirty:
                out.append((pv, self.b, self.sum / self.vt if self.vt > 0 else None, self.mn, self.mx,
                            min(1.0, self.vt / self.w), self.worst if self.worst is not None else self.sev,
                            self.v, self.sev))
            self.dirty = False
            self._reset()
            self.b = end
            if t >= self.b + self.w:      # intervals the state holds through: not stored
                self.b += math.floor((t - self.b) / self.w) * self.w
            self.t = self.b

    def change(self, t, value, severity, pv, out):
        """A new state from t on (value None: no valid value)."""
        if self.b is None:
            self.b = self.t = math.floor(t / self.w) * self.w
        self.advance(t, pv, out)
        t = max(t, self.t)
        self._take(t)
        self.v, self.sev, self.dirty = value, severity, True

    def touch(self):
        """Store the open interval even if nothing changes in it (after a gap of the logger)."""
        self.dirty = True


class Batch:
    def __init__(self, now):
        self.now = now
        self.raw, self.changes, self.seconds, self.minutes, self.events = [], [], [], [], []
        self.connections = []       # (pv, connected, t): the pv table
        self.through = None         # (raw, seconds, minutes): complete up to these times
        self.started = None         # the logger's start, in its first batch
        self.counted = 0            # rows counted into the buffer

    def rows(self):
        return len(self.raw) + len(self.changes) + len(self.seconds) + len(self.minutes) + len(self.events)


def fmt(ch, value, text):
    """A value as the event log writes it: the word of an enumeration with its number, a number
    with up to 10 significant digits, a text as it is."""
    if value is None and text is None:
        return None
    if ch.kind == "enum":
        return "%s (%d)" % (text, value) if text not in (None, "") else "%d" % value
    if ch.kind == "text":
        return text
    return "%.10g" % value


class Recorder:
    """The rules of R2 to R7 for every channel. Called from one thread only."""

    def __init__(self, channels, clock_skew=10.0, close_delay=2.0):
        self.channels = {ch.id: ch for ch in channels}
        self.clock_skew = clock_skew        # seconds: a time stamp further from the clock is replaced
        self.close_delay = close_delay      # seconds: an interval is closed this long after its end
        self.batch = Batch(None)
        self.pending = []                   # [deadline, event, context channel]: waiting for the reason
        self.drives = {}                    # mode PV id -> channels it drives
        for ch in channels:
            if ch.driver:
                self.drives.setdefault(ch.driver[0], []).append(ch)

    # --- events from Channel Access --------------------------------------------------------------
    def update(self, ch, value, text, severity, status, stamp, now):
        """A monitor update: value (number, or None for a text), text (state word or string),
        the IOC's severity, status and time stamp, the logger's clock."""
        b = self.batch
        if ch.driver and not ch.seen:          # its first value: the loop may be in PID already
            mode = self.channels.get(ch.driver[0])
            ch.driven = bool(mode and mode.connected and mode.value == ch.driver[1]
                             and mode.severity is not None and mode.severity < INVALID)
        initial = not ch.seen or not ch.connected
        t, flags = self._time(ch, stamp, now, initial, b)
        if isinstance(value, float) and math.isnan(value):
            value = None
        old_text, old_sev = (ch.known_text, ch.known_severity)
        ch.value, ch.text, ch.severity, ch.status, ch.t = value, text, severity, status, t
        if not ch.connected:
            if ch.seen:
                b.events.append((now, ch.id, "connection", "lost", "back", None, severity, status, None))
            ch.connected = True
            b.connections.append((ch.id, True, now))
        ch.seen = True
        if ch.table:
            getattr(b, ch.table).append((ch.id, t, value, text, severity, status, flags))
        valid = value if severity is not None and severity < INVALID and value is not None else None
        if ch.signal:
            for w, agg in ch.aggs.items():
                agg.change(t, valid, severity if severity is not None else INVALID, ch.id,
                           b.seconds if w == 1 else b.minutes)
        if severity != old_sev:
            if not (old_sev is None and severity == NO_ALARM):
                b.events.append((t, ch.id, "alarm", SEVERITY[old_sev] if old_sev is not None else None,
                                 SEVERITY[severity], None, severity, status,
                                 STATUS[status] if status is not None and 0 <= status < len(STATUS) else None))
            ch.known_severity = severity
        if ch.tier == "events" and not ch.driven:
            new = fmt(ch, value, text)
            if new != old_text:
                event = [t, ch.id, "set" if ch.written else "state", old_text, new, value, severity, status, None]
                if ch.context in self.channels:
                    self.pending.append([now + CONTEXT_WAIT, event, self.channels[ch.context]])
                else:
                    b.events.append(tuple(event))
                ch.known_text = new
        if ch.id in self.drives:
            for target in self.drives[ch.id]:
                self._drive(target, value == target.driver[1] and severity is not None and severity < INVALID, t, b)
        self._resolve(lambda p: p[2] is ch)

    def _resolve(self, ready):
        """Write the mode events whose reason has come (or whose wait is over), with that reason."""
        keep = []
        for p in self.pending:
            if ready(p):
                other = p[2]
                p[1][8] = "%s: %s" % (other.name, fmt(other, other.value, other.text)) if other.seen else None
                self.batch.events.append(tuple(p[1]))
            else:
                keep.append(p)
        self.pending = keep

    def _drive(self, ch, driven, t, b):
        """A loop took over the PV it writes (PID) or gave it back: from here its updates are a
        signal (raw and intervals), or set commands again (changes and events)."""
        if driven == ch.driven or not ch.seen:
            ch.driven = driven and ch.seen
            return
        t = max(t, ch.t)
        ch.t = t
        valid = ch.value if ch.severity is not None and ch.severity < INVALID and ch.value is not None else None
        if driven:
            ch.driven = True
            b.raw.append((ch.id, t, ch.value, ch.text, ch.severity, ch.status, FLAG_DRIVEN))
            for w, agg in ch.aggs.items():
                agg.change(t, valid, ch.severity if ch.severity is not None else INVALID, ch.id, b.seconds if w == 1 else b.minutes)
        else:
            ch.driven = False
            b.raw.append((ch.id, t, None, None, None, None, FLAG_DRIVEN))
            for w, agg in ch.aggs.items():
                agg.change(t, None, INVALID, ch.id, b.seconds if w == 1 else b.minutes)
            b.changes.append((ch.id, t, ch.value, ch.text, ch.severity, ch.status, FLAG_DRIVEN))
            ch.known_text = fmt(ch, ch.value, ch.text)

    def disconnect(self, ch, now):
        if not ch.connected:
            return
        b = self.batch
        ch.connected = False
        b.connections.append((ch.id, False, now))
        b.events.append((now, ch.id, "connection", "connected", "lost", None, None, None, None))
        for target in self.drives.get(ch.id, []):
            self._drive(target, False, now, b)          # a loop not seen is not in PID
        self._gap(ch, max(now, ch.t), 0, b)

    def _gap(self, ch, t, flags, b):
        ch.gap_t = t
        ch.t = max(ch.t, t)
        if ch.table:
            getattr(b, ch.table).append((ch.id, t, None, None, None, None, flags))
        if ch.signal:
            for w, agg in ch.aggs.items():
                if agg.b is not None:
                    agg.change(t, None, INVALID, ch.id, b.seconds if w == 1 else b.minutes)

    def _time(self, ch, stamp, now, initial, b):
        """R7: the time a row is stored under, and its flags."""
        flags = 0
        if stamp < NEVER_PROCESSED_BEFORE:
            t, flags = now, FLAG_UDF_TIME
        elif stamp > now + self.clock_skew or (not initial and stamp < now - self.clock_skew):
            t, flags = now, FLAG_CLOCK
            if not ch.clock_warned:
                ch.clock_warned = True
                b.events.append((now, ch.id, "logger", None, "clocks apart", None, None, None,
                                 "IOC time stamp %+.1f s from the logger's clock: stored under the logger's time"
                                 % (stamp - now)))
        else:
            t = stamp
        if t <= ch.gap_t:          # a value from before a gap (or before the logger's start)
            t, flags = max(now, ch.gap_t), flags | FLAG_RESUMED
        return max(t, ch.t), flags

    # --- the logger's own gaps -----------------------------------------------------------------
    def start(self, through, known, now):
        """At the start: through is (raw, seconds, minutes) of the last run, or None; known is
        {pv id: (severity, value text)} from the event log. Writes the gap rows of the time the
        logger did not run."""
        for ch in self.channels.values():
            if ch.id in known:
                ch.known_severity, ch.known_text = known[ch.id]
        if through is None:
            return
        self.gap_rows(through, self.batch)

    def gap_rows(self, through, b):
        """A gap for every channel from `through` on: raw/changes at through[0], the intervals at
        the first interval not stored (through[1], through[2])."""
        raw_t, sec_t, min_t = through
        for ch in self.channels.values():
            ch.gap_t = max(ch.gap_t, raw_t)
            if ch.table:
                getattr(b, ch.table).append((ch.id, raw_t, None, None, None, None, FLAG_LOGGER))
            for w, agg in ch.aggs.items():
                t = sec_t if w == 1 else min_t
                (b.seconds if w == 1 else b.minutes).append((ch.id, t, None, None, None, 0.0, INVALID, None, INVALID))

    def resume(self, through, now):
        """After rows were lost (the buffer was full): a gap from the end of what was written,
        then the present state of every connected channel, so that nothing is held across."""
        b = Batch(now)
        self.gap_rows(through, b)
        for ch in self.channels.values():
            if ch.connected and ch.seen:
                ch.t = max(ch.t, now)
                if ch.table:
                    getattr(b, ch.table).append((ch.id, ch.t, ch.value, ch.text, ch.severity, ch.status, FLAG_RESUMED))
                if ch.signal:
                    for agg in ch.aggs.values():
                        agg.touch()
        return b

    # --- once per tick --------------------------------------------------------------------------
    def tick(self, now, final=False):
        """Close the intervals that ended close_delay ago; hand over the batch of this tick
        (final: with every event still waiting for its reason)."""
        self._resolve(lambda p: final or p[0] <= now)
        b = self.batch
        edge = now - self.close_delay
        for ch in self.channels.values():
            for w, agg in ch.aggs.items():
                agg.advance(edge, ch.id, b.seconds if w == 1 else b.minutes)
        b.now = now
        b.through = (now, math.floor(edge), math.floor(edge / 60) * 60)
        self.batch = Batch(None)
        return b
