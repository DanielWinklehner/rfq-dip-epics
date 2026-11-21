"""The control interface: one JSON object per line in, one per line out.

Commands (key "cmd"): info, fault, clear, get, set, release, stats.
Every reply has "ok": true, or "ok": false with "error". Bad input never crashes the simulator.
"""

import asyncio
import json
import math
import numbers

from .simulator import Unsupported


def _need_signal(sim, req):
    name = req.get("signal")
    if not isinstance(name, str):
        raise ValueError("'signal' (a signal name) is required")
    if name not in sim.signals:
        raise ValueError("no signal %r (signals: %s)" % (name, ", ".join(sorted(sim.signals))))
    return sim.signals[name]


def _only(req, *allowed):
    extra = sorted(set(req) - {"cmd"} - set(allowed))
    if extra:
        raise ValueError("unknown argument(s) %s" % ", ".join(extra))


def _cmd_info(sim, req):
    _only(req)
    return sim.info()


def _cmd_fault(sim, req):
    _only(req, "mode", "unit", "duration", "ms")
    sim.add_fault(req.get("mode"), req.get("unit"), req.get("duration"), req.get("ms"))
    return {"faults": sim.fault_list()}


def _cmd_clear(sim, req):
    _only(req, "mode", "unit")
    return {"cleared": sim.clear_faults(req.get("mode"), req.get("unit")),
            "faults": sim.fault_list()}


def _cmd_get(sim, req):
    _only(req, "signal")
    sim.step_couplings()
    if "signal" in req:
        sig = _need_signal(sim, req)
        return dict(signal=sig.name, **sig.state())
    return {"signals": {name: s.state() for name, s in sorted(sim.signals.items())},
            "faults": sim.fault_list()}


def _cmd_set(sim, req):
    _only(req, "signal", "value")
    sig = _need_signal(sim, req)
    value = req.get("value")
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
        raise ValueError("'value' must be a finite number")
    sim.step_couplings()
    sig.force(value)
    return dict(signal=sig.name, **sig.state())


def _cmd_release(sim, req):
    _only(req, "signal")
    sig = _need_signal(sim, req)
    sim.step_couplings()
    sig.release()
    return dict(signal=sig.name, **sig.state())


def _cmd_stats(sim, req):
    _only(req, "reset")
    reset = req.get("reset", False)
    if not isinstance(reset, bool):
        raise ValueError("'reset' must be true or false")
    result = sim.stats.as_dict()
    if reset:
        sim.stats.reset()
    return result


COMMANDS = {
    "info": _cmd_info, "fault": _cmd_fault, "clear": _cmd_clear, "get": _cmd_get,
    "set": _cmd_set, "release": _cmd_release, "stats": _cmd_stats,
}


def handle_command(sim, line):
    """One request line (str or bytes) -> one reply dict."""
    try:
        req = json.loads(line)
    except (ValueError, UnicodeDecodeError) as exc:
        return {"ok": False, "error": "not JSON: %s" % exc}
    if not isinstance(req, dict):
        return {"ok": False, "error": "expected a JSON object"}
    cmd = req.get("cmd")
    if cmd not in COMMANDS:
        return {"ok": False, "error": "unknown command %r, known: %s" % (cmd, ", ".join(COMMANDS))}
    try:
        result = COMMANDS[cmd](sim, req)
    except (ValueError, TypeError, Unsupported) as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # a device bug must not kill the control port
        sim.log.exception("control command %r failed", req)
        return {"ok": False, "error": "internal error: %s" % exc}
    result["ok"] = True
    return result


async def serve_control(sim, host, port):
    async def client(reader, writer):
        sim.track_handler()
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                if not line.strip():
                    continue
                reply = handle_command(sim, line)
                writer.write((json.dumps(reply, default=str) + "\n").encode())
                await writer.drain()
        except (ConnectionError, OSError, asyncio.LimitOverrunError, ValueError):
            pass
        finally:
            writer.close()

    return await asyncio.start_server(client, host, port)
