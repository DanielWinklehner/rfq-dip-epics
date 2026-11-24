"""coupling.py - the coupling of the case "dipolescan": the magnet current, as the DAQ service
measures it, sets the current at the picoammeter simulator's input.

    python coupling.py coupling.yaml

Every period_s: read the service's status port ({"cmd": "status"}), take the monitor channel's
volts, scale them as the service does (offset + per_volt * volts, from the service's own
configuration), evaluate the spectrum of coupling.yaml there and set the picoammeter simulator's
signal "current" through its control port. The magnet current the coupling sees is the one the
service read last (the IOC asks every 0.5 s).

While the service does not answer (stopped by a test), the last current set is kept: the magnet
keeps its field, the picoammeter keeps its input. A picoammeter that does not take the value (its
control port gone) is tried again every period. One log line per change of state.

A model of this case, not of MIST-2 (coupling.yaml says why).
"""
import json
import logging
import math
import socket
import sys
import time

import yaml

from mist2sim.control import ControlClient, ControlError

log = logging.getLogger("coupling")


def load(path):
    with open(path) as handle:
        c = yaml.safe_load(handle)
    with open(c["service"]["config"]) as handle:
        daq = yaml.safe_load(handle)
    ch = next(x for x in daq["channels"] if x["id"] == c["service"]["channel"])
    c["scale"] = (float(ch.get("offset", 0.0)), float(ch["per_volt"]))
    return c


def spectrum(c, magnet_a):
    """The picoammeter current (A) at a magnet current (A)."""
    y = float(c["background_a"])
    for p in c["peaks"]:
        x0 = float(c["first_peak_a"]) * math.sqrt(float(p["mass"]))
        y += float(p["height_a"]) * math.exp(-0.5 * ((magnet_a - x0) / float(p["sigma_a"])) ** 2)
    return y


def magnet_current(c):
    s = c["service"]
    with socket.create_connection((s["host"], s["status_port"]), timeout=1.0) as sock:
        sock.sendall(b'{"cmd": "status"}\n')
        line = sock.makefile().readline()
    reply = json.loads(line)
    volts = reply["status"]["channels"][s["channel"]]["volts"]
    if volts is None:
        raise ValueError("the service has no reading of %s" % s["channel"])
    offset, per_volt = c["scale"]
    return offset + per_volt * float(volts)


def main(path):
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s coupling %(message)s")
    c = load(path)
    p = c["picoammeter"]
    log.info("peaks at %s A of magnet current, background %g A",
             ", ".join("%.4g" % (c["first_peak_a"] * math.sqrt(x["mass"])) for x in c["peaks"]),
             c["background_a"])
    pico, state = None, None
    while True:
        try:
            current = magnet_current(c)
            new = "following the service"
        except (OSError, ValueError, KeyError) as exc:
            current, new = None, "service not answering (%s): the last current kept" % exc
        if new != state:
            log.info("%s", new)
            state = new
        if current is not None:
            try:
                if pico is None:
                    pico = ControlClient(p["host"], p["control_port"], timeout=2.0)
                pico.set(p["signal"], spectrum(c, current))
            except (OSError, ControlError, ValueError) as exc:
                log.info("picoammeter control port: %s", exc)
                if pico is not None:
                    try:
                        pico.close()
                    except OSError:
                        pass
                pico = None
        time.sleep(float(c["period_s"]))


if __name__ == "__main__":
    main(sys.argv[1])
