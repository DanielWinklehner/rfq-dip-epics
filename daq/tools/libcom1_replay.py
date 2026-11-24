"""Replays AVR/libcom1/tests/script.hpp through the protocol of mist2daq and prints the same
transcript as AVR/libcom1/tests/replay_host.cpp (the real library). compare_libcom1.sh diffs them.

    python3 tools/libcom1_replay.py [--script path/to/script.hpp]        (in daq/)

The step table and the check of the script's device are taken from the simulator's replay tool
(emulation/sim/tools/libcom1_replay.py), so both tools read the script the same way.
"""

import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))

from mist2daq.protocol import Channel, Device, f32  # noqa: E402

SIM_TOOL = os.path.join(REPO, "emulation", "sim", "tools", "libcom1_replay.py")
DEFAULT_SCRIPT = os.path.join(REPO, "AVR", "libcom1", "tests", "script.hpp")


def sim_tool():
    spec = importlib.util.spec_from_file_location("sim_libcom1_replay", SIM_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def script_device():
    """The device of script.hpp, built with mist2daq's Device. Returns (device, state)."""
    values = [f32(v) for v in (4091.71, 0.0, -2.5, 23.4609375, 1.5e-7, 0.0)]
    state = {"setpoint": 0.0, "timeouts": 0, "values": values}

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
    device = Device(channels, "ScriptDevice", "1.2.3", out_buffer=160)
    device.set_comm_timeout(500, on_timeout)
    return device, state


def run(steps, emit):
    device, state = script_device()
    for time_ms, line in steps:
        shown = line if line is not None else "(tick)"
        emit("> " + shown.split("\0")[0][:45])            # header[48] in script.hpp
        received = "" if line is None else line[:31]      # g_line[32] in script.hpp
        reply, frames, _ = device.service(time_ms, received)
        if reply is not None:
            emit(reply)
        for frame in frames:
            emit(frame)
        if device.comm_lost:
            emit("  [comm lost]")
    emit("timeouts=%d" % state["timeouts"])
    emit("DONE")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--script", default=DEFAULT_SCRIPT)
    args = parser.parse_args()
    tool = sim_tool()
    with open(args.script) as f:
        text = f.read()
    tool.check_device(text)
    run(tool.parse_steps(text), lambda s: sys.stdout.write(s + "\n"))


if __name__ == "__main__":
    main()
