"""Replays AVR/libcom1/tests/script.hpp through the Python libcom1 engine and prints the same
transcript as AVR/libcom1/tests/replay_host.cpp.

    python3 tools/libcom1_replay.py --format avr|g [--script path/to/script.hpp]

The step table is parsed from the header, so a changed conversation is picked up. The device of
the script (8 channels, identity, 500 ms timeout) is rebuilt here; the header is checked for the
lines it is rebuilt from, so a changed device fails loudly instead of diffing silently.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from mist2sim.devices.libcom1 import Channel, Engine, f32  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SCRIPT = os.path.join(HERE, "..", "..", "..", "AVR", "libcom1", "tests", "script.hpp")

# The parts of script.hpp that the device below is rebuilt from.
EXPECTED = [
    "static float g_values[6] = { 4091.71f, 0.0f, -2.5f, 23.4609375f, 1.5e-7f, 0.0f };",
    "static float get_idx(uint8_t i) { return g_values[i] * 2.0f; }",
    "static void  on_timeout() { ++g_timeouts; g_setpoint = -1.0f; }",
    "Channel{ 'a', 1, &get_a1, nullptr },",
    "Channel{ 'a', 2, &get_a2, nullptr },",
    "Channel{ 'a', 3, &get_a3, nullptr },",
    "Channel{ 'b', 1, &get_b1, nullptr },",
    "Channel{ 'b', 2, &get_b2, nullptr },",
    "Channel{ 's', 1, &get_sp, &set_sp },",
    "Channel{ 'w', 1, nullptr, &set_sp },",
    "IndexedChannel('x', 1, &get_idx, &set_idx, 5),",
    "static mist1::com1::IOHandler<160> io(read_step, write_reply);",
    "static mist1::com1::SerialDevice<160, 8> device(io, lookup);",
    'device.set_identity("ScriptDevice", "1.2.3");',
    "device.set_comm_timeout(500, &on_timeout);",
    "static char g_line[32];",
    "char header[48];",
]

_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "0": "\0", "\\": "\\", '"': '"', "'": "'"}


def c_unescape(body):
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        nxt = body[i + 1]
        if nxt == "x":
            m = re.match(r"[0-9a-fA-F]+", body[i + 2:])
            out.append(chr(int(m.group(0), 16) & 0xFF))
            i += 2 + len(m.group(0))
        elif nxt in "01234567":
            m = re.match(r"[0-7]{1,3}", body[i + 1:])
            out.append(chr(int(m.group(0), 8) & 0xFF))
            i += 1 + len(m.group(0))
        else:
            out.append(_ESCAPES[nxt])
            i += 2
    return "".join(out)


def parse_steps(text):
    """[(time_ms, line or None), ...] from `static const Step steps[] = { ... };`"""
    # Drop // and /* */ comments, keeping string literals intact
    text = re.sub(r'("(?:[^"\\\n]|\\.)*")|//[^\n]*|/\*.*?\*/',
                  lambda m: m.group(1) or "", text, flags=re.S)
    m = re.search(r"static\s+const\s+Step\s+steps\s*\[\s*\]\s*=\s*\{(.*?)\}\s*;", text, re.S)
    if not m:
        raise SystemExit("script.hpp: step table not found")
    table = m.group(1)
    steps = []
    pos = 0
    step_re = re.compile(r'\s*\{\s*(\d+)\s*,\s*("(?:[^"\\]|\\.)*"|nullptr)\s*\}\s*,?')
    while pos < len(table.rstrip()):
        s = step_re.match(table, pos)
        if not s:
            raise SystemExit("script.hpp: cannot parse the step table near %r" % table[pos:pos + 40])
        line = None if s.group(2) == "nullptr" else c_unescape(s.group(2)[1:-1])
        steps.append((int(s.group(1)), line))
        pos = s.end()
    return steps


def check_device(text):
    flat = " ".join(text.split())
    missing = [e for e in EXPECTED if " ".join(e.split()) not in flat]
    if missing:
        raise SystemExit("script.hpp: the device definition changed, update libcom1_replay.py:\n  "
                         + "\n  ".join(missing))


def run(steps, number_format, emit):
    values = [f32(v) for v in (4091.71, 0.0, -2.5, 23.4609375, 1.5e-7, 0.0)]
    state = {"setpoint": 0.0, "timeouts": 0}

    def set_sp(v):
        state["setpoint"] = v

    def set_idx(v):
        values[5] = v

    def on_timeout():
        state["timeouts"] += 1
        state["setpoint"] = -1.0

    channels = [
        Channel("a", 1, lambda: values[0]),
        Channel("a", 2, lambda: values[1]),
        Channel("a", 3, lambda: values[2]),
        Channel("b", 1, lambda: values[3]),
        Channel("b", 2, lambda: values[4]),
        Channel("s", 1, lambda: state["setpoint"], set_sp),
        Channel("w", 1, None, set_sp),
        Channel("x", 1, lambda: f32(values[5] * 2.0), set_idx),
    ]
    device = Engine(channels, "ScriptDevice", "1.2.3", number_format, out_buffer=160)
    device.set_comm_timeout(500, on_timeout)

    for time_ms, line in steps:
        shown = line if line is not None else "(tick)"
        emit("> " + shown.split("\0")[0][:45])            # header[48] in script.hpp
        received = "" if line is None else line[:31]      # g_line[32] in script.hpp
        out = device.service(time_ms, received)
        if out.reply is not None:
            emit(out.reply)
        for frame in out.frames:
            emit(frame)
        if device.comm_lost:
            emit("  [comm lost]")
    emit("timeouts=%d" % state["timeouts"])
    emit("DONE")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--format", choices=("avr", "g"), required=True)
    parser.add_argument("--script", default=DEFAULT_SCRIPT)
    args = parser.parse_args()
    with open(args.script) as f:
        text = f.read()
    check_device(text)
    out = sys.stdout
    run(parse_steps(text), args.format, lambda s: out.write(s + "\n"))


if __name__ == "__main__":
    main()
