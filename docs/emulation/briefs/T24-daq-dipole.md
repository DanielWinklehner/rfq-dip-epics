You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T24: the dipole magnet supplies become PVs. They have an analog interface only and hang on an NI USB-6001 at the lab computer, which LabVIEW drives today. You build a small Python service that owns the NI box and serves it to an IOC, the records, and a device test case. No hardware is available.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t24`, on branch `emu/t24-daq-dipole`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never touch the main checkout or another worktree.
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo. Python tooling runs in the image `mist2-tools:dev`, the IOC in `mist2-ioc:dev`.
- A device case (`emulation/devtest/run.sh <case>`) is its own Compose project on its own network and needs no lock. You do not need the full emulation. Two other engineers work on this machine at the same time (T23, T25), in their own worktrees.
- Long commands may exceed your tool's time limit: run them in the background, write output and exit code to files, and wait for them.
- Your shell's working directory may reset between commands: start every command with `cd /home/daniel/code/rfq-dip-epics/.claude/worktrees/t24 && ...`.
- Some file tools refuse `.db` files as binary: read them with `cat`, and check every edit with `git diff`.
- Never run `rm` with a shell variable in its path. Leave no container and no process running when you finish.

# Read first
1. `plan/controls.yaml`: the devices `magnets` and `ni_desk`, the host `lab_pc`, work package WP11.
2. `AVR/libcom1/README.md`: the libcom1 protocol, version 2 (commands, replies, errors, identity, the communication timeout).
3. `EPICS/README`, and the databases of the libcom1 devices that are served over TCP: `EPICS/Db/faradaycup.db`, `turbo.db`, `libcom1_device.db`, `libcom1.proto` (`read_all_array`, `com1_setLink_flt_ack`, the identity entries), `first_contact.db` with its header.
4. `emulation/sim/mist2sim/devices/libcom1.py` and `emulation/sim/README.md`: the simulator of a libcom1 device and how it is checked against the real library (`emulation/sim/run_tests.sh`).
5. `emulation/devtest/run.sh` (header: `sim.cmd` replaces the simulator command), `emulation/devtest/compose.yaml`, the cases `faradaycup` and `libcom1_devices`.
6. `loops/README.md` and `loops/systemd/`: how a Python service of this system is installed on a real computer.

# What is known, and what is not
Known (plan, owner): the supplies are old and have an analog interface only, "analog 0-10 V"; an NI USB-6001 at the lab computer; the lab computer runs Ubuntu (owner, 2026-11-24; version not known); proposed PVs `dipole:current:set` and `dipole:current:get`, both in A.

Not known: how many supplies there are and which channels of the NI box they use, volts per ampere in either direction, the current range, the polarity, whether a supply has an enable or other inputs, whether it needs slow changes, and whether NI's driver for Linux serves the USB-6001 on that computer. Every one of these is a configuration value or stays out, and is listed in your report. Do not invent values for the machine.

# What to build
R1. **Service `daq/mist2daq`:** Python 3.8 or later, standard library and PyYAML; `nidaqmx` is imported by the real backend only. It owns one NI box and serves its channels as a libcom1 protocol 2 device over TCP, so that the IOC uses the unmodified `libcom1.proto` and `libcom1_device.db`, as for the Optas. Channels come from a configuration file: libcom1 channel, direction, physical channel, engineering unit per volt and offset, limits in the unit and in volts, a name. Identity and channel list as the protocol defines them.
R2. **Two backends** behind one small interface: `sim`, in memory, where an input can follow an output with a gain and a first-order lag (a supply's current monitor); and `nidaqmx`, written from NI's documentation, each call with its source, marked NOT VERIFIED. Find out from NI's own documentation whether NI-DAQmx for Linux supports the USB-6001 and on which Ubuntu versions, and report it with the source. If it does not, say so and name what else could serve this box or replace it; build none of that.
R3. **What the service does by itself: nothing.** At its start it writes no output. An output's value is "not known" until the first set of this run, and the IOC must see that as such, not as zero. A set outside a channel's limits is refused with the protocol's error and not applied. Say what happens to the outputs when the service stops, and when no client has asked for a while (the protocol has a communication timeout: the default here is to hold; a ramp to zero is a setting, off by default, for the owner to decide).
R4. **`EPICS/Db/dipole.db`** with macros for the prefix (default `dipole`), port, channels, unit, limits: `$(DEVICE):current:set` (acknowledged set, drive limits), `$(DEVICE):current:get`, and what the service holds as the set value, so that after an IOC restart the set record shows the truth and nothing is written (the rule of every request record in this system: see `first_contact.db`; use it if it fits an analog value, or say why not). Alarms as `EPICS/README` demands: the service silent means INVALID, not the last value. The polling as the other libcom1 databases do it.
R5. **On the lab computer:** `daq/README.md` with the installation (virtual environment, a systemd unit under `daq/systemd/`, the configuration file to edit, how to see that it works with a voltmeter before a supply is connected), marked not verified. A configuration file for the dipole with every unknown value marked ASSUMED.
R6. **`docs/emulation/DAQ.md`:** design, the configuration key by key, what the service does at start, stop, lost client and wrong input, the table of unknowns.

# Tests
1. Unit tests without EPICS (`python3 -m unittest discover -s daq/tests -t daq`): the protocol (every command and error of the README, long and broken lines), scaling and offset in both directions, limits, the `sim` backend, "not known" before the first set.
2. The service's replies against the libcom1 simulator's, command by command (the simulator is checked against the real library), or against the real library the way `emulation/sim/run_tests.sh` does it. Say which, and what differs.
3. A device case `emulation/devtest/dipole`: the service with the `sim` backend as the case's simulator (`sim.cmd`), an IOC with `dipole.db` and `libcom1_device.db`. A set is acknowledged, the output voltage is the value divided by the scale (read it from the service, not from the IOC), the read-back follows with the lag; identity records valid; a set beyond the drive limit is clamped by the record; a set beyond the service's limit (loaded with wider record limits in the case) is refused, the record goes into alarm, the output is unchanged; the service stopped: every record INVALID within the time you state, and valid again after its restart, with the set value "not known" shown as such; the IOC restarted: nothing written to the service (count its set commands), the set record shows the held value; a second client connects while the IOC is connected: say what happens; the update rate of the read-back, measured.
See each test of 3 fail once without the property it checks, and say how.

# Files you own
`daq/**`, `EPICS/Db/dipole.db`, `emulation/devtest/dipole/**`, `docs/emulation/DAQ.md`. Not yours: everything else, in particular `plan/controls.yaml`, the registry, the IOCs' `st.cmd`, `EPICS/Db/libcom1.proto` and the other databases, `emulation/sim`, `emulation/tests`, `docs/emulation/STATUS.md`, `PLAN.md`, `README.md`. If you find you need a change there (a protocol entry, something in the test harness), stop at that point and report it with the reason.

The devices stay "later" in the plan and are loaded by no IOC of the emulation yet: which computer's IOC serves them is decided with the owner after this task. So `make -C emulation plan-check` must pass unchanged, and the system suite is not touched.

# Acceptance (the lead runs these from your worktree)
    python3 -m unittest discover -s daq/tests -t daq              (in mist2-tools:dev: say the exact docker command)
    emulation/devtest/run.sh emulation/devtest/dipole
    make -C emulation plan-check
All exit 0.

# Rules
- Do not invent facts. A claim about the NI box or its driver comes from NI's documentation with the page; a claim about libcom1 from `AVR/libcom1`; a claim about EPICS or StreamDevice from the source in our image (`docker run --rm --entrypoint sh mist2-ioc:dev -c '...'`, base under `/opt/epics/base`, StreamDevice under `/opt/epics/support/StreamDevice/src`).
- No change outside the files you own. If something here turns out wrong or cannot be built as described, stop and say so in the report instead of building something else.
- A report that says "done" is not evidence: give the commands you ran, their exit codes and the numbers they printed, and say plainly what you did not do or could not show.

# Final report, with these headings
MODEL, BRANCH, BUILT, HOW IT WORKS (a set and a read step by step; start, stop, lost client), NI ON LINUX (what the documentation says, with sources), VERIFIED (commands, exit codes, times, how each test was seen to fail), DECISIONS (with reasons), ASSUMED, NOT VERIFIED, QUESTIONS FOR THE OWNER, NEEDS THE LEAD (text for STATUS.md and for the plan), COMMITS.
