You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T2. A lead engineer wrote this brief, will run your acceptance test himself, and will merge your branch. Other engineers work in parallel on other files, so stay inside the files you own.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t2`, on branch `emu/t2-sim-core`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. `/home/daniel/code/rfq-dip-epics` itself is the lead's worktree: never edit, stage or commit anything there. Check that `git -C /home/daniel/code/rfq-dip-epics/.claude/worktrees/t2 branch --show-current` prints `emu/t2-sim-core` and that `docs/emulation/DESIGN.md` exists in your worktree. If not, stop and report.
- Commit on that branch only. Small commits with clear messages. Never commit on `master` or `emulated-iocs`. Never push, never open a pull request.
- Read first: `docs/emulation/DESIGN.md` (the approved design, the part "Simulators" in section 2 is yours), `docs/emulation/PLAN.md`, `AVR/libcom1/README.md` (the protocol), `AVR/libcom1/*.hpp` (the real library), `AVR/libcom1/tests/` (Makefile, `script.hpp`, `replay_host.cpp`, `dtostre_shim.hpp`), `EPICS/Db/libcom1.proto`, and the firmware sketches `AVR/devices/SolenoidValveBox/SolenoidValveBox/SolenoidValveBox.ino` and `AVR/Thermocouple/Thermocouple.ino`.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Available on the host: Python 3.10 with PyYAML (no pytest), g++, make, Docker without sudo.

# Background
The real system has devices on serial lines (RS-232, RS-485 buses, USB serial) and on TCP. For development without hardware, every device is replaced by a software simulator that speaks the real wire protocol over TCP. An EPICS IOC (asyn + StreamDevice) connects to the simulators with `drvAsynIPPortConfigure` exactly as it would connect to a serial port, using the same database and protocol files as for the real devices. Polling rates in the emulator must match reality, and the tests must be able to make every device misbehave.

You build the simulator CORE that all device simulators share, and the FIRST device simulator: libcom1, our Arduino communication library. Four other engineers will write further device modules (Matsusada high-voltage supply bus, TDK supply, Edwards gauge, MKS RS-485 mass flow controller, a talk-only RS-232 monitor) against your core, in parallel, each touching only their own new module file. So your core's interface and its one-page documentation are as important as the code.

# Files you own
Everything under `emulation/sim/` EXCEPT the directory `emulation/sim/config/` (the lead creates it later, do not create it). Nothing else. If you need a change elsewhere, describe it in your report.

Suggested layout (change it if you have a better one, but keep the package name and the two entry points):

    emulation/sim/mist2sim/            the package
        __main__.py                    python -m mist2sim --config <file.yaml>
        core/                          transport, timing, signals, faults, control interface
        control.py                     ControlClient, the client side of the control interface
        devices/libcom1.py             the libcom1 engine and simulator
    emulation/sim/tests/               unit tests (standard library unittest)
    emulation/sim/examples/            example configurations
    emulation/sim/README.md            the interface documentation
    emulation/sim/run_tests.sh         the acceptance test

# Requirements

## General
- Python 3.10 or newer (must run on 3.10 and 3.12). Standard library plus PyYAML, nothing else. asyncio.
- Small and readable. These are "small Python programs", not a framework. No feature that is not asked for here.
- One process can run several simulators (one per bus or device), each on its own TCP port. `python -m mist2sim --config file.yaml` starts all simulators listed in the file, listens on all interfaces, logs to stdout, and exits cleanly on SIGTERM and SIGINT.
- Device modules are discovered automatically: a new file in `mist2sim/devices/` that registers a simulator type must work WITHOUT editing any existing file.

## Transport and timing
- One simulator = one TCP port = one serial line or bus. The IOC connects once and stays connected, and it reconnects by itself after a drop. A new connection replaces an old one.
- Framing is configurable per simulator: input terminator and output terminator are arbitrary byte strings (CR, LF, CR LF, or something like `;FF`).
- Half duplex, one transaction at a time, in order of arrival.
- **Each reply is delayed by the time its characters would need on the real line**: `(request bytes + reply bytes, terminators included) x bits_per_char / baud + turnaround_ms`, counted from the arrival of the request. `baud`, `bits_per_char` (default 10) and `turnaround_ms` are per-simulator settings. A request that gets no reply still occupies the line for its own transmission time. Requests that arrive while the line is busy wait their turn. The timing must hold when requests are queued back to back (no drift, no cumulative error from sleeping).
- Devices can also send lines on their own (libcom1 stream frames, talk-only devices). Unsolicited output respects the line timing as well and is never inserted into the middle of a reply.
- A bus simulator answers for several unit addresses. The base class takes a request, lets the subclass decide which unit it addresses (or all units, or none), and routes it. A request for an address that does not exist gets no answer, as on a real bus.

## Signals
- A named value with plausible behaviour: it follows its target with a time constant (first order), carries a little Gaussian noise on read, and can have limits and a quantisation step. All parameters are settings.
- Time comes from an injectable clock, so that unit tests run with a fake clock and do not sleep.
- Every signal of a simulator is visible and settable through the control interface (below). That is the hook for a later plant model: an external process reads actuators (for example a supply's output current) and writes process values (for example a pressure), without any change to the device code. A signal written from outside stays under outside control until it is released.
- A small in-process hook for couplings INSIDE one simulator (example: a relay signal that makes a "speed" signal ramp up, which in turn switches a status signal). Keep it minimal: a callable that is stepped with `dt` and the signals.

## Faults: one common control interface
Every simulator has a second TCP port, the control port (default: device port + 1000). Protocol: one JSON object per line in, one JSON object per line out. The tests and the later plant model use it. Commands:
- `info`: name, type, unit addresses, signal names, settings.
- `fault`: `mode` is one of `silent` (takes input, never answers), `close` (closes the connection and refuses new ones while active), `garbage` (answers with a corrupted reply, correctly timed), `trip` (device-specific: the device module decides what a trip is, for example "output switches off"), `slow` (extra delay in ms). Optional `unit` (one address on a bus, default the whole simulator) and optional `duration` in seconds, after which the fault clears by itself.
- `clear`: remove faults.
- `get` (all signals and active faults, or one signal), `set` (signal, value), `release` (signal).
- `stats`: transactions total and per unit, bytes in and out, time the line was busy, since start or since the last `stats` with `reset`. The lead uses this to compare measured update rates with the bus arithmetic.
Unknown commands and bad arguments get an error object, never a crash and never silence.
Provide `mist2sim.control.ControlClient` (synchronous, standard library sockets, usable from pytest) with one method per command.

## Configuration file
YAML, one list of simulators. Each entry: `name`, `type`, `port`, optional `control_port`, line settings (`baud`, `bits_per_char`, `turnaround_ms`, terminators), and `options` that belong to the device type. Unknown keys are an error with a clear message, so that a typing mistake cannot pass silently.

## libcom1 simulator
- A pure, deterministic ENGINE without I/O and without clock access: it gets a received line and the device time in ms, and returns the replies, exactly as `SerialDevice::service(now_ms)` of the real library does. Commands `A`, `g`, `s`, `S`, `I`, `P`, the legacy `q01...`, every error reply `ERR0` to `ERR7`, streaming frames, the communication timeout, input line length limit and output buffer limit as in the library.
- Two number formats, selectable per device: the Arduino AVR format (`dtostre`, see `LIBCOM1_USE_DTOSTRE=1` and `tests/dtostre_shim.hpp`) and plain `%g` (as on the Arduino Opta). The real library computes in 32-bit `float`. Reproduce that where it changes the output.
- **Proof against the real library, this is the core of your acceptance test.** Do not edit anything under `AVR/`. Build `replay_host` from `AVR/libcom1/tests/replay_host.cpp` on this PC with g++ in both variants (`-DLIBCOM1_USE_DTOSTRE=1` and `=0`; use your own build commands in `emulation/sim/`, the sanitizer flags of the original Makefile are optional). Write a Python replay that takes the conversation from `AVR/libcom1/tests/script.hpp` (parse the step table from the header, so that a changed script is picked up; the device definition of the script, 8 channels with their getters and setters, the identity and the 500 ms timeout, you rebuild in Python), drives your engine with it and prints the same transcript. `diff` must show ZERO differences in both variants. If a difference remains, do not paper over it: find out whether your engine or your reading of the script is wrong, and report anything you cannot resolve.
- On top of the engine, the simulator type `libcom1`, fully described by configuration, so that the lead can define a valve box, a thermocouple board or a PLC without writing Python: identity, firmware string, number format, line ending of the replies (LF as over TCP, or CR LF as `Serial.println` sends), and the channel list in query-all order. Each channel has an identifier such as `s1`, is readable and/or writable, and is bound to a signal with one of a few simple behaviours: a constant, a noisy analog value, or a value that reads back what was written to it (a relay or valve). A fault mode `trip` is not needed for libcom1 (answer with an error object).
- Two example configurations that match the real firmware: `examples/valvebox.yaml` (SolenoidValveBox: 8 channels s1 to s8, read back what was set, 115200 baud, AVR format, CR LF) and `examples/thermocouple.yaml` (16 channels in the order of the sketch, 19200 baud).

## Documentation (`emulation/sim/README.md`, two pages at most)
- How to start a simulator and talk to it by hand.
- The configuration keys.
- The control protocol with one example per command.
- **How to write a new device module**: the minimal single-unit device and the minimal multi-unit bus, as two short complete examples. This section is what the four other engineers will work from, so write it for them and test the examples.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    emulation/sim/run_tests.sh

It must exit 0 and print a short summary. It does, in this order:
1. All unit tests (`python3 -m unittest discover`), on the host's Python 3.10. They cover at least: reply delay matches the formula at 9600 and 115200 baud within 2 ms plus 2 percent for a single request and for 20 queued requests (real sockets, real time, this one test may take a few seconds); a multi-unit bus with one unit silenced answers for the others; every fault mode including timed clearing; `close` and reconnect; signals with a fake clock; the control interface including bad input; configuration errors.
2. The libcom1 replay against the real library, both number formats, with the number of compared lines printed.
3. An end-to-end check: start `python -m mist2sim` with `examples/valvebox.yaml` as a subprocess, send `I`, `A`, `Ss11`, `gs1` and a bad command over TCP, check the replies, inject `silent` through `ControlClient`, see that a query times out, clear the fault, see that it answers again, read `stats`.
Also run the unit tests once on Python 3.12 (for example in a `python:3.12-slim` container with PyYAML installed) and say in your report that they pass there.

# Rules
- Do not invent facts about the protocol: the real library in `AVR/libcom1` is the reference, and the replay proves it.
- Leave no process and no container running when you finish.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t2-sim-core @ <commit>, worktree <absolute path>
    BUILT: what exists now, one line per part
    INTERFACE: the base classes and functions a device module uses, with signatures (the lead copies this into four briefs)
    VERIFIED: the output summary of run_tests.sh, the replay line counts, the Python 3.12 run
    DECISIONS: choices you made that the brief left open, each with one reason
    ASSUMED: anything you could not verify
    NEEDS THE LEAD: changes outside your files, open questions, anything that did not work
