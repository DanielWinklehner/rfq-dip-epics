"""Settings of the logger (environment, logger/env.template) and its PV list (the registry).

The PV list is not written by hand: plan/registry.py writes the tier of every PV into the
registry (key "log", from the section logging of plan/controls.yaml), and the tiers' life times
under "logging". A PV added to the plan is logged after `make -C emulation registry` and a
restart of the logger.
"""
import json
import os

NUMBER_TYPES = {"ai", "ao", "calc", "calcout", "longin", "longout"}
ENUM_TYPES = {"bi", "bo", "mbbi", "mbbo"}
TEXT_TYPES = {"stringin", "stringout", "lsi", "lso"}
LONG_STRINGS = {"lsi", "lso"}      # read through the field VAL$ (more than 40 characters)


def env(name, default=None, cast=str):
    value = os.environ.get(name, "")
    return cast(value) if value != "" else default


class Settings:
    def __init__(self):
        self.registry = env("MIST2LOG_REGISTRY", "/config/registry.json")
        self.db = {"host": env("MIST2LOG_DB_HOST", "127.0.0.1"), "port": env("MIST2LOG_DB_PORT", 5432, int),
                   "dbname": env("MIST2LOG_DB_NAME", "mist2log"), "user": env("MIST2LOG_DB_USER", "mist2log"),
                   "password": env("MIST2LOG_DB_PASSWORD", "")}
        self.reader_password = env("MIST2LOG_READER_PASSWORD", "")
        # Rows kept in memory while the database is lost or slow; what does not fit is counted
        # and logged. 2 000 000 rows: about 4 hours of the full emulation, about 300 MB (LOGGER.md, sizing).
        self.buffer_rows = env("MIST2LOG_BUFFER_ROWS", 2000000, int)
        # A time stamp further than this from the logger's clock is replaced by it (R7, P33).
        self.clock_skew = env("MIST2LOG_CLOCK_SKEW_S", 10.0, float)
        # An interval of tiers 2 and 3 is closed this long after its end (late monitor updates).
        self.close_delay = env("MIST2LOG_CLOSE_DELAY_S", 2.0, float)
        # The state records in the rack IOC (EPICS/Db/logger_status.db)
        self.status_prefix = env("MIST2LOG_STATUS_PREFIX", "LOGGER")


class Channel:
    """One PV of the registry that is logged."""

    def __init__(self, name, spec, device):
        self.name, self.device = name, device
        self.tier, self.type = spec["log"], spec["type"]
        self.role, self.egu, self.states = spec.get("role"), spec.get("egu"), spec.get("states")
        self.written = spec["access"] == "w"
        self.kind = "enum" if self.type in ENUM_TYPES else "text" if self.type in TEXT_TYPES else "number"
        self.ca_name = name + ".VAL$" if self.type in LONG_STRINGS else name
        self.context = None     # name of the PV whose value goes with each event of this one


def load_registry(path):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    channels = []
    for group in ("iocs", "devices"):
        for device, entry in data[group].items():
            roles = entry.get("roles", {})
            for name, spec in entry["pvs"].items():
                if spec.get("log", "none") == "none":
                    continue
                ch = Channel(name, spec, device)
                # A loop's mode is logged with the reason of its last hand-back or refusal.
                if spec.get("role") == "mode" and "reason" in roles:
                    ch.context = roles["reason"]
                channels.append(ch)
    return channels, data["logging"]["tiers"]
