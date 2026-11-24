"""The configuration file of mist2daq: checked completely before anything is opened.

Every key is described in docs/emulation/DAQ.md ("Configuration"). Unknown keys are errors, so a
typing mistake does not silently leave a default in place.
"""

import math

import yaml


class ConfigError(Exception):
    pass


SERVICE_DEFAULTS = {
    "identity": "mist2daq",       # ID= of the identity reply
    "listen_host": "127.0.0.1",   # where the IOC connects (libcom1 over TCP)
    "listen_port": 5100,
    "status_host": "127.0.0.1",   # read-only status (JSON lines); status_port null = none
    "status_port": None,
    "takeover_s": 10.0,           # a second client replaces the first only after this silence
    "comm_timeout_s": 5.0,        # libcom1 communication timeout; 0 = off
    "on_comm_lost": "hold",       # hold | ramp_to_zero
    "ramp_period_s": 0.1,         # step period of a ramp to zero
}

TERMINALS = ("DEFAULT", "RSE", "NRSE", "DIFF")


class ChannelConfig:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __repr__(self):
        return "ChannelConfig(%s)" % self.__dict__


class Config:
    def __init__(self, service, backend, channels, source=""):
        self.service, self.backend, self.channels, self.source = service, backend, channels, source

    @property
    def outputs(self):
        return [c for c in self.channels if c.direction == "out"]

    @property
    def inputs(self):
        return [c for c in self.channels if c.direction == "in"]


def _number(where, value, key):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ConfigError("%s: %s must be a finite number, not %r" % (where, key, value))
    return float(value)


def _pair(where, value, key):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ConfigError("%s: %s must be [low, high]" % (where, key))
    lo, hi = (_number(where, v, key) for v in value)
    if not lo < hi:
        raise ConfigError("%s: %s must have low < high, not %r" % (where, key, list(value)))
    return lo, hi


def _unknown(where, given, allowed):
    extra = sorted(set(given) - set(allowed))
    if extra:
        raise ConfigError("%s: unknown key(s) %s; allowed: %s" % (where, ", ".join(extra), ", ".join(sorted(allowed))))


CHANNEL_KEYS = {
    "out": {"id", "name", "direction", "physical", "unit", "per_volt", "offset", "limits", "volts",
            "ramp_rate"},
    "in": {"id", "name", "direction", "physical", "unit", "per_volt", "offset", "volts", "terminal"},
}


def _channel(i, spec, service):
    where = "channels[%d]" % i
    if not isinstance(spec, dict):
        raise ConfigError("%s: expected a mapping" % where)
    cid = spec.get("id")
    if not isinstance(cid, str) or len(cid) != 2 or not cid[0].isalpha() or not cid[1].isdigit():
        raise ConfigError("%s: id must be one letter and one digit, like o1, not %r" % (where, cid))
    where = "channel %s" % cid
    direction = spec.get("direction")
    if direction not in CHANNEL_KEYS:
        raise ConfigError("%s: direction must be out or in, not %r" % (where, direction))
    _unknown(where, spec, CHANNEL_KEYS[direction])
    for key in ("name", "physical", "unit", "per_volt", "volts"):
        if key not in spec:
            raise ConfigError("%s: %s is missing" % (where, key))
    for key in ("name", "physical", "unit"):
        if not isinstance(spec[key], str) or (key != "unit" and not spec[key]):
            raise ConfigError("%s: %s must be a text" % (where, key))
    per_volt = _number(where, spec["per_volt"], "per_volt")
    if per_volt == 0:
        raise ConfigError("%s: per_volt must not be 0" % where)
    c = ChannelConfig(id=cid, name=spec["name"], direction=direction, physical=spec["physical"],
                      unit=spec["unit"], per_volt=per_volt,
                      offset=_number(where, spec.get("offset", 0.0), "offset"),
                      volts=_pair(where, spec["volts"], "volts"))
    if direction == "in":
        c.terminal = spec.get("terminal", "DEFAULT")
        if c.terminal not in TERMINALS:
            raise ConfigError("%s: terminal must be one of %s" % (where, ", ".join(TERMINALS)))
        return c
    if "limits" not in spec:
        raise ConfigError("%s: limits is missing" % where)
    c.limits = _pair(where, spec["limits"], "limits")
    # The limits in the unit and in volts must allow at least one common value.
    v_lo, v_hi = sorted(((c.limits[0] - c.offset) / per_volt, (c.limits[1] - c.offset) / per_volt))
    if v_hi < c.volts[0] or v_lo > c.volts[1]:
        raise ConfigError("%s: limits %r (%g to %g V) and volts %r have no value in common" % (
            where, list(c.limits), v_lo, v_hi, list(c.volts)))
    c.ramp_rate = spec.get("ramp_rate")
    if service["on_comm_lost"] == "ramp_to_zero":
        if c.ramp_rate is None:
            raise ConfigError("%s: on_comm_lost is ramp_to_zero, so ramp_rate (%s per second) is needed"
                              % (where, c.unit))
        c.ramp_rate = _number(where, c.ramp_rate, "ramp_rate")
        if c.ramp_rate <= 0:
            raise ConfigError("%s: ramp_rate must be > 0" % where)
        if not c.limits[0] <= 0.0 <= c.limits[1]:
            raise ConfigError("%s: on_comm_lost is ramp_to_zero but 0 %s is outside limits %r"
                              % (where, c.unit, list(c.limits)))
        zero_v = -c.offset / per_volt
        if not c.volts[0] <= zero_v <= c.volts[1]:
            raise ConfigError("%s: 0 %s is %g V, outside volts %r" % (where, c.unit, zero_v, list(c.volts)))
    elif c.ramp_rate is not None:
        c.ramp_rate = _number(where, c.ramp_rate, "ramp_rate")
    return c


def parse(data, source="<config>"):
    if not isinstance(data, dict):
        raise ConfigError("%s: the file must be a mapping with service, backend, channels" % source)
    _unknown(source, data, {"service", "backend", "channels"})
    service = dict(SERVICE_DEFAULTS)
    given = data.get("service") or {}
    if not isinstance(given, dict):
        raise ConfigError("service: expected a mapping")
    _unknown("service", given, SERVICE_DEFAULTS)
    service.update(given)
    for key in ("identity", "listen_host", "status_host"):
        if not isinstance(service[key], str) or not service[key]:
            raise ConfigError("service: %s must be a text" % key)
    if any(c in service["identity"] for c in ";\r\n"):
        raise ConfigError("service: identity must not contain ';' or line ends")
    for key in ("listen_port", "status_port"):
        v = service[key]
        if v is None and key == "status_port":
            continue
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 65535:
            raise ConfigError("service: %s must be a TCP port number" % key)
    for key in ("takeover_s", "comm_timeout_s", "ramp_period_s"):
        service[key] = _number("service", service[key], key)
        if service[key] < 0:
            raise ConfigError("service: %s must be >= 0" % key)
    if service["ramp_period_s"] <= 0:
        raise ConfigError("service: ramp_period_s must be > 0")
    if service["on_comm_lost"] not in ("hold", "ramp_to_zero"):
        raise ConfigError("service: on_comm_lost must be hold or ramp_to_zero")
    if service["on_comm_lost"] == "ramp_to_zero" and service["comm_timeout_s"] == 0:
        raise ConfigError("service: on_comm_lost ramp_to_zero needs comm_timeout_s > 0")

    backend = data.get("backend")
    if not isinstance(backend, dict) or backend.get("type") not in ("sim", "nidaqmx"):
        raise ConfigError("backend: a mapping with type sim or nidaqmx is needed")
    _unknown("backend", backend, {"type", "device", "product_type", "sim"})

    specs = data.get("channels")
    if not isinstance(specs, list) or not specs:
        raise ConfigError("channels: a non-empty list is needed")
    channels = [_channel(i, s, service) for i, s in enumerate(specs, 1)]
    for key in ("id", "physical", "name"):
        seen = [getattr(c, key) for c in channels]
        dup = sorted({x for x in seen if seen.count(x) > 1})
        if dup:
            raise ConfigError("channels: %s not unique: %s" % (key, ", ".join(dup)))
    return Config(service, backend, channels, source)


def load(path):
    with open(path) as handle:
        try:
            data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ConfigError("%s: %s" % (path, exc)) from None
    return parse(data, path)
