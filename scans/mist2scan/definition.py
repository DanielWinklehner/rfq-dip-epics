"""The scan definition: a YAML file, checked key by key, and the list of points. No EPICS import.

Every key is listed in KEYS below and explained in docs/emulation/SCAN.md, section 3. A key that
is not known is an error, not ignored: a misspelt "tolerence" must not silently become a default.
"""
import math

import yaml

OPS = ("==", "!=", "<", "<=", ">", ">=")
ENDS = ("previous", "stay")
NOT_SETTLED = ("skip", "end")
MAX_POINTS = 100000
DEFAULT_OUTPUT = "scan-data"
DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READBACK_LOST_AFTER = 5.0

KEYS = {
    "": {"name", "description", "actuator", "points", "detectors", "dwell", "conditions", "end",
         "output", "connect_timeout"},
    "actuator": {"set", "readback", "held", "tolerance", "settle_timeout", "settle_time",
                 "max_step", "step_pause", "limits", "on_not_settled", "readback_lost_after"},
    "points": {"start", "stop", "step", "values"},
    "detector": {"pv", "name", "required"},
    "condition": {"pv", "op", "value"},
}


class DefinitionError(ValueError):
    pass


def clean(x, scale=0.0):
    """A point without the noise of the floating-point arithmetic: 0.1 * 3 is 0.3, not
    0.30000000000000004, and -0.3 + 3 * 0.1 is 0, not 5.6e-17. Twelve significant digits (of
    the point, or of `scale`, the size of the scan, for points near 0) are far finer than any
    set point."""
    if abs(x) < 1e-12 * scale:
        return 0.0
    return float("%.12g" % x)


def range_points(start, stop, step):
    """start, start + step, ... up to stop. The step's sign must point from start to stop; stop
    is included when it lies on the grid (within 1e-9 of a step), otherwise the last point is the
    last grid point before it. Each point is start + k * step, not a running sum."""
    if step == 0:
        raise DefinitionError("points.step: must not be 0")
    span = stop - start
    if span != 0 and (span > 0) != (step > 0):
        raise DefinitionError("points.step: %g goes away from stop (start %g, stop %g)"
                              % (step, start, stop))
    n = int(math.floor(span / step + 1e-9))
    if n + 1 > MAX_POINTS:
        raise DefinitionError("points: %d points, more than %d" % (n + 1, MAX_POINTS))
    scale = max(abs(start), abs(stop), abs(step))
    return [clean(start + k * step, scale) for k in range(n + 1)]


def part_steps(a, b, max_step):
    """The writes that take the actuator from a to b, none larger than max_step: n equal steps,
    the last one exactly b. Every value lies between a and b. max_step None: one write."""
    if max_step is None or abs(b - a) <= max_step:
        return [b]
    n = int(math.ceil(abs(b - a) / max_step - 1e-9))
    lo, hi = min(a, b), max(a, b)
    out = [min(hi, max(lo, a + (b - a) * k / n)) for k in range(1, n)]
    return out + [b]


class Detector:
    def __init__(self, pv, name, required):
        self.pv, self.name, self.required = pv, name, required


class Condition:
    def __init__(self, pv, op, value):
        self.pv, self.op, self.value = pv, op, value

    def holds(self, value):
        v, w = float(value), self.value
        return {"==": v == w, "!=": v != w, "<": v < w, "<=": v <= w, ">": v > w,
                ">=": v >= w}[self.op]

    def text(self):
        return "%s %s %g" % (self.pv, self.op, self.value)


class Definition:
    """The checked definition. `data` is the definition as it runs (overrides applied), for the
    file definition.yaml of the scan."""

    def __init__(self, data, source=None):
        self.source = source
        self.data = data
        _keys(data, "", "")
        self.name = _text(data, "name", "")
        self.description = data.get("description", "")
        if not isinstance(self.description, str):
            raise DefinitionError("description: must be text")

        a = _mapping(data, "actuator", "")
        _keys(a, "actuator", "actuator.")
        self.set_pv = _text(a, "set", "actuator.")
        self.readback_pv = _text(a, "readback", "actuator.")
        self.held_pv = _text(a, "held", "actuator.") if "held" in a else None
        if self.held_pv == self.set_pv:
            raise DefinitionError("actuator.held: must be another PV than the set PV")
        self.readback_lost_after = (
            _number(a, "readback_lost_after", "actuator.", positive=True)
            if "readback_lost_after" in a else DEFAULT_READBACK_LOST_AFTER)
        self.tolerance = _number(a, "tolerance", "actuator.", positive=True)
        self.settle_timeout = _number(a, "settle_timeout", "actuator.", positive=True)
        self.settle_time = _number(a, "settle_time", "actuator.", minimum=0.0)
        if a.get("max_step", "missing") is None:
            self.max_step = None
        else:
            self.max_step = _number(a, "max_step", "actuator.", positive=True)
        self.step_pause = _number(a, "step_pause", "actuator.", minimum=0.0)
        limits = a.get("limits")
        if (not isinstance(limits, list) or len(limits) != 2
                or not all(_is_number(x) for x in limits)):
            raise DefinitionError("actuator.limits: must be [minimum, maximum]")
        self.limits = (float(limits[0]), float(limits[1]))
        if not self.limits[0] < self.limits[1]:
            raise DefinitionError("actuator.limits: minimum %g is not below maximum %g"
                                  % self.limits)
        self.on_not_settled = a.get("on_not_settled")
        if self.on_not_settled not in NOT_SETTLED:
            raise DefinitionError("actuator.on_not_settled: must be one of %s"
                                  % ", ".join(NOT_SETTLED))

        p = _mapping(data, "points", "")
        _keys(p, "points", "points.")
        if "values" in p:
            if set(p) & {"start", "stop", "step"}:
                raise DefinitionError("points: either values or start, stop, step, not both")
            values = p["values"]
            if not isinstance(values, list) or not values or not all(_is_number(x) for x in values):
                raise DefinitionError("points.values: must be a list of numbers")
            self.points = [float(x) for x in values]
        else:
            start, stop, step = (_number(p, k, "points.") for k in ("start", "stop", "step"))
            self.points = range_points(start, stop, step)

        dets = data.get("detectors")
        if not isinstance(dets, list) or not dets:
            raise DefinitionError("detectors: must be a list with at least one detector")
        self.detectors = []
        for n, d in enumerate(dets):
            where = "detectors[%d]." % n
            if not isinstance(d, dict):
                raise DefinitionError("detectors[%d]: must be a mapping" % n)
            _keys(d, "detector", where)
            pv = _text(d, "pv", where)
            name = d.get("name", pv)
            if not isinstance(name, str) or not name or any(c in name for c in ",\"\n"):
                raise DefinitionError(where + "name: text without commas or quotes")
            required = d.get("required")
            if not isinstance(required, bool):
                raise DefinitionError(where + "required: must be true or false")
            self.detectors.append(Detector(pv, name, required))
        names = [d.name for d in self.detectors]
        if len(set(names)) != len(names) or "readback" in names:
            raise DefinitionError("detectors: names must be different from each other and "
                                  "from 'readback'")
        if self.set_pv in [d.pv for d in self.detectors]:
            raise DefinitionError("detectors: the set PV cannot be a detector")

        self.dwell = _number(data, "dwell", "", minimum=0.0)

        conds = data.get("conditions", [])
        if not isinstance(conds, list):
            raise DefinitionError("conditions: must be a list")
        self.conditions = []
        for n, c in enumerate(conds):
            where = "conditions[%d]." % n
            if not isinstance(c, dict):
                raise DefinitionError("conditions[%d]: must be a mapping" % n)
            _keys(c, "condition", where)
            op = c.get("op")
            if op not in OPS:
                raise DefinitionError(where + "op: must be one of %s" % " ".join(OPS))
            self.conditions.append(Condition(_text(c, "pv", where), op,
                                             _number(c, "value", where)))

        end = data.get("end")
        if end in ENDS:
            self.end = end
        elif _is_number(end):
            self.end = float(end)
        else:
            raise DefinitionError("end: must be previous, stay or a number")

        self.output = data.get("output", DEFAULT_OUTPUT)
        if not isinstance(self.output, str) or not self.output:
            raise DefinitionError("output: must be a directory name")
        self.connect_timeout = (_number(data, "connect_timeout", "", positive=True)
                                if "connect_timeout" in data else DEFAULT_CONNECT_TIMEOUT)

    def pvs(self):
        """Every PV the scan uses, the set PV first."""
        names = [self.set_pv, self.readback_pv] + ([self.held_pv] if self.held_pv else [])
        names += [d.pv for d in self.detectors]
        names += [c.pv for c in self.conditions]
        return list(dict.fromkeys(names))


def load(path, start=None, stop=None, step=None, dwell=None, output=None):
    """Read a definition file and apply the command line's overrides."""
    with open(path, encoding="utf-8") as handle:
        try:
            data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise DefinitionError("%s: not valid YAML: %s" % (path, exc))
    if not isinstance(data, dict):
        raise DefinitionError("%s: must be a mapping" % path)
    return make(data, path, start, stop, step, dwell, output)


def make(data, source=None, start=None, stop=None, step=None, dwell=None, output=None):
    data = _copy(data)
    given = {k: v for k, v in (("start", start), ("stop", stop), ("step", step)) if v is not None}
    if given:
        points = data.get("points")
        if not isinstance(points, dict):
            raise DefinitionError("points: missing")
        if "values" in points:
            if len(given) != 3:
                raise DefinitionError("the definition lists its points: --start, --stop and "
                                      "--step must all be given to replace them")
            points = {}
        points.update(given)
        data["points"] = points
    if dwell is not None:
        data["dwell"] = dwell
    if output is not None:
        data["output"] = output
    return Definition(data, source)


def _copy(x):
    if isinstance(x, dict):
        return {k: _copy(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_copy(v) for v in x]
    return x


def _keys(mapping, kind, where):
    unknown = sorted(str(k) for k in mapping if k not in KEYS[kind])
    if unknown:
        raise DefinitionError("%sunknown key%s: %s (known: %s)"
                              % (where, "s" if len(unknown) > 1 else "", ", ".join(unknown),
                                 ", ".join(sorted(KEYS[kind]))))


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _mapping(data, key, where):
    value = data.get(key)
    if not isinstance(value, dict):
        raise DefinitionError("%s%s: missing or not a mapping" % (where, key))
    return value


def _text(data, key, where, default=None):
    value = data.get(key, default)
    if not isinstance(value, str) or (default is None and not value):
        raise DefinitionError("%s%s: missing or not text" % (where, key))
    return value


def _number(data, key, where, positive=False, minimum=None):
    value = data.get(key)
    if not _is_number(value):
        raise DefinitionError("%s%s: missing or not a number" % (where, key))
    value = float(value)
    if positive and not value > 0:
        raise DefinitionError("%s%s: must be greater than 0" % (where, key))
    if minimum is not None and value < minimum:
        raise DefinitionError("%s%s: must be at least %g" % (where, key, minimum))
    return value
