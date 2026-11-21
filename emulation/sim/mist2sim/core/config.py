"""Configuration: a YAML list of simulators. Unknown keys are errors."""

import yaml

from .registry import IMPORT_ERRORS, TYPES, load_devices
from .simulator import LINE_DEFAULTS, ConfigError

ENTRY_KEYS = {"name", "type", "port", "control_port", "options"} | set(LINE_DEFAULTS)


def load_config(path):
    """Read and check a configuration file. Returns the list of entries (dicts)."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except OSError as exc:
        raise ConfigError("cannot read %s: %s" % (path, exc)) from None
    except yaml.YAMLError as exc:
        raise ConfigError("%s is not valid YAML: %s" % (path, exc)) from None
    return check_config(data, str(path))


def check_config(data, where="configuration"):
    if not isinstance(data, list) or not data:
        raise ConfigError("%s: expected a non-empty list of simulators" % where)
    load_devices()
    names, ports = set(), {}
    for i, entry in enumerate(data, 1):
        label = "%s, simulator %d" % (where, i)
        if not isinstance(entry, dict):
            raise ConfigError("%s: expected a mapping" % label)
        if isinstance(entry.get("name"), str):
            label = "%s (%s)" % (label, entry["name"])
        unknown = sorted(set(entry) - ENTRY_KEYS)
        if unknown:
            raise ConfigError("%s: unknown key(s) %s; allowed: %s" % (
                label, ", ".join(unknown), ", ".join(sorted(ENTRY_KEYS))))
        for key in ("name", "type", "port"):
            if key not in entry:
                raise ConfigError("%s: key %r is missing" % (label, key))
        if not isinstance(entry["name"], str) or not entry["name"]:
            raise ConfigError("%s: name must be a non-empty string" % label)
        if entry["name"] in names:
            raise ConfigError("%s: name %r is used twice" % (label, entry["name"]))
        names.add(entry["name"])
        if entry["type"] not in TYPES:
            broken = "; modules that failed to import: %s" % IMPORT_ERRORS if IMPORT_ERRORS else ""
            raise ConfigError("%s: unknown type %r; known: %s%s" % (
                label, entry["type"], ", ".join(sorted(TYPES)), broken))
        for key in ("port", "control_port"):
            if key not in entry:
                continue
            p = entry[key]
            if isinstance(p, bool) or not isinstance(p, int) or not 0 <= p <= 65535:
                raise ConfigError("%s: %s must be a port number, not %r" % (label, key, p))
        port = entry["port"]
        control = entry.get("control_port", port + 1000 if port else 0)
        for p in (port, control):
            if p and p in ports:
                raise ConfigError("%s: port %d is already used by %s" % (label, p, ports[p]))
            if p:
                ports[p] = entry["name"]
    return data


def build(entry, clock=None, rng=None):
    """Create the simulator for one configuration entry."""
    load_devices()
    cls = TYPES[entry["type"]]
    line = {k: v for k, v in entry.items() if k in LINE_DEFAULTS}
    return cls(entry["name"], port=entry["port"], control_port=entry.get("control_port"),
               options=entry.get("options"), clock=clock, rng=rng, **line)
