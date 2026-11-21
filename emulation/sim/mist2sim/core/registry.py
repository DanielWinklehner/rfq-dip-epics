"""Simulator types: @register("name") and automatic discovery of mist2sim/devices/*.py."""

import importlib
import logging
import pkgutil

TYPES = {}
IMPORT_ERRORS = {}

log = logging.getLogger("mist2sim")


def register(type_name):
    """Class decorator: makes a Simulator subclass available as `type: <type_name>`."""
    def deco(cls):
        if type_name in TYPES and TYPES[type_name] is not cls:
            raise ValueError("simulator type %r is registered twice" % type_name)
        cls.TYPE = type_name
        TYPES[type_name] = cls
        return cls
    return deco


def load_devices():
    """Import every module in mist2sim.devices. A module that fails to import is logged and
    skipped, so one broken module does not take the others down."""
    from .. import devices
    for info in pkgutil.iter_modules(devices.__path__):
        name = "%s.%s" % (devices.__name__, info.name)
        try:
            importlib.import_module(name)
        except Exception as exc:  # report, do not crash the other simulators
            IMPORT_ERRORS[info.name] = "%s: %s" % (type(exc).__name__, exc)
            log.error("device module %s failed to import: %s", info.name, IMPORT_ERRORS[info.name])
    return TYPES
