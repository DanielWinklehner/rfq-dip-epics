You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T5: the mass flow controller, the Faraday cup readout and the two turbopump controllers. A lead engineer wrote this brief, will run your acceptance test himself, and will merge your branch. Other engineers work in parallel on other files, so stay inside the files you own.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t5`, on branch `emu/t5-mfc-fc-turbo`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. `/home/daniel/code/rfq-dip-epics` itself is the lead's worktree: never edit, stage or commit anything there. Check that `git -C /home/daniel/code/rfq-dip-epics/.claude/worktrees/t5 branch --show-current` prints `emu/t5-mfc-fc-turbo`. If not, stop and report.
- Commit on that branch only. Small commits with clear messages. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo. The images `mist2-ioc:dev` and `mist2-tools:dev` exist already (`make -C emulation build` rebuilds them from cache if needed).

# Read first
1. `docs/emulation/DESIGN.md`: the approved design, sections 1, 3 and 4 (section 4 is the turbopump controller in full).
2. `emulation/sim/README.md`: the simulator core, "How to write a new device module", the control interface, and the simulator type `libcom1`, which is configured entirely in YAML.
3. `emulation/README.md` and `emulation/devtest/example/`: the harness that runs simulators, one IOC and your tests together.
4. `EPICS/README`, `EPICS/Db/libcom1.proto`, `EPICS/Db/libcom1_device.db`, and `EPICS/Db/solenoidbox.db` as the model of a libcom1 device database on this branch (array record polled with `read_all_array`, element records with `CA MS` links, acknowledged sets). `AVR/libcom1/examples/EthernetExample/EthernetExample.ino` shows libcom1 over TCP on an Arduino Opta.
5. The lab's mass flow controller files from 2023: `reference/lab-2023/EPICS/Db/IOC.mfc.db`, `mfc.proto`, and the commented lines for it in `reference/lab-2023/EPICS/st.cmd`.

# Three devices, three different levels of knowledge
Be exact about what is known and what is not. This brief tells you which is which.

## A. Mass flow controller MKS GV50A (RS-485 multi-drop, works in the lab)
**Known**: the lab's files of 2023, which are a DRAFT: only the set point is implemented, the lines in `st.cmd` are commented out, and the protocol file carries notes about mismatches. Address 254, 9600 baud, message layout `@@@254<command>;FF`, reply `@@@000ACK<value>;FF`. PV names in the lab: `$(DEVICE):getSP`, `$(DEVICE):setSP`, `$(DEVICE):getWink`, `$(DEVICE):setWink`, loaded with `DEVICE=MFC`. The version that really runs in the lab is not available before next week.
**To find out**: the MKS RS-485 protocol of the G series. The G and I series manual (`https://www.mks.com/mam/celum/celum_assets/resources/GISeriesMFCs-MAN.pdf`, section "RS485 Communication Description") says the format is the one of the older MKS 1179 and 1479 controllers and refers to "MKS G-Series MFC, RS485 Supplement (1046411-001)". I did not find that supplement. Search for it, and for the RS-485 documentation of the 1179/1479 family, and for open-source drivers of these devices. Establish: message framing (is there a CR, what exactly ends a message), checksum rules (`FF`), `ACK` and `NAK` with their error codes, the commands for set point (query and write), measured flow, full scale, valve state or drive level, and status.
**Build**:
- `EPICS/Db/mfc.db` and `mfc.proto`: keep the four lab PV names and their meaning (the set point is in percent of full scale in the lab's draft: check that against the protocol and keep the lab's meaning), add ONE new record `$(DEVICE):getFlow` (measured flow). Address as a macro with default 254. A write is acknowledged by the device: a `NAK` or a missing answer must end in an alarm on the set record. Sensible polling (flow fast by macro, the rest slower). Units and precision.
- Simulator `mks_rs485`: a multi-drop bus with several addresses, the framing and replies as documented, flow following the set point with a time constant, full scale and gas as settings, signals for a later plant model (set point, flow).
- Everything you could not establish from a document: a setting with a comment, and a line under ASSUMED in your report. The lead will compare with the lab's real files next week.

## B. Faraday cup readout (Arduino Opta, firmware and PVs unknown)
**Known**: nothing but the hardware. **Assumed, by decision of the lead**: the Opta speaks libcom1 over TCP like `EthernetExample`, and serves one channel with the cup current.
**Build**: `EPICS/Db/faradaycup.db`, modelled on the libcom1 databases of this branch: array record, `$(DEVICE):current:get` (unit A, the lead loads it with `DEVICE=FC`), the channel position as a macro. Loaded together with `libcom1_device.db`. No simulator code: a `libcom1` entry in your test configuration (number format `%g`, LF line ending, TCP, an identity string of your choice, the current as a noisy signal around 1e-6 A that a plant model can drive). Keep it this small: it will be replaced when the firmware is known.

## C. Two Leybold TURBOTRONIK NT 20 turbopump controllers (checked against the operating instructions, partly unknown)
**Known** (DESIGN.md section 4, from the operating instructions GA 05.208/8): each controller is started and stopped through remote-control inputs, reports through three relays (NORMAL above 80 % of target speed, ACCEL, FAILURE), a failure is reset by the STOP command, and an RS-232 port sends "all main internal parameters" every 8 s at 9600 baud in a format that is NOT published.
**Decided**: ONE Arduino Opta serves both controllers, speaking libcom1 over TCP. Its firmware does not exist yet, so you define its channel map, and the firmware will be written to match. Use this one, in query-all order: `r1`, `r2` (relay outputs: run pump 1, run pump 2; writable and readable), `r3`, `r4` (spare relays, writable and readable), `n1`, `a1`, `f1` (inputs of pump 1: NORMAL, ACCEL, FAILURE contacts, readable), `n2`, `a2`, `f2` (the same for pump 2). Identity `TurboOpta`.
**Build**:
- `EPICS/Db/turbo.db`: the Opta (array record, loaded with `DEVICE=TURBO` and together with `libcom1_device.db`) and, per pump, the PVs of the table in DESIGN.md section 4 that come from the Opta: `$(P):start:set` (acknowledged set), `:start:get`, `:atspeed:get`, `:accel:get`, `:failure:get` (MAJOR alarm), `:state:get` (stopped, accelerating, normal, failure, inconsistent, with alarm severities, built from the three relays and the run command as the relay table in the operating instructions implies; a controller without power shows NO failure contact, so "run commanded, but neither accelerating nor normal nor failure" must not look healthy). `P` is `TURBO1` or `TURBO2`. Decide whether the per-pump records are a second database file loaded twice or part of `turbo.db` with macros, and keep the loading to one or two obvious lines per pump.
- `EPICS/Db/nt20_monitor.db` and `nt20_monitor.proto`: ONE listen-only port per pump (the IOC never sends on it). Records: `$(P):raw:get` (the last record as text, unparsed), `$(P):age:get` (seconds since the last record, alarm above 20 s), `$(P):speed:get` (Hz) and `$(P):current:get` (A). **The record format is unknown.** Invent a plausible placeholder format, state at the top of the protocol file AND in the simulator that it is invented and must be replaced after a capture from a real unit, and build so that replacing it means editing the protocol file and one function of the simulator, nothing else. `raw` and `age` must work whatever the format is (within one line of text ending in CR or LF; say what you assume about the line ending and make it a setting).
- Simulator `nt20_monitor`: a device that only talks. It owns the pump model: on "run", ACCEL closes and the speed ramps up over a configurable time, above 80 % NORMAL closes and ACCEL opens, on "stop" the pump runs down, `trip` raises FAILURE (and the pump brakes) until a stop command resets it. It sends one record every 8 s (setting) with speed and motor current.
- **Coupling.** In reality the NT 20 is wired to the Opta: the Opta's relay starts it, its three contacts drive the Opta's inputs. In the emulator the Opta is a `libcom1` simulator on its own port, and each NT 20 is an `nt20_monitor` simulator on its own port. Couple them through the public control interface, the same way the later plant model will: the `nt20_monitor` simulator is configured with the address of the Opta simulator's control port and the names of the signals for "run" (read) and for the three contacts (written), and exchanges them a few times per second. If the control interface cannot do this cleanly, describe the problem and the smallest change to the core that would solve it, and do not change the core yourself.

# Files you own
- `emulation/sim/mist2sim/devices/mks_rs485.py`, `emulation/sim/mist2sim/devices/nt20_monitor.py`, one unit test file each under `emulation/sim/tests/`
- `EPICS/Db/mfc.db`, `EPICS/Db/mfc.proto`, `EPICS/Db/faradaycup.db`, `EPICS/Db/turbo.db` (and a per-pump file if you split it), `EPICS/Db/nt20_monitor.db`, `EPICS/Db/nt20_monitor.proto`
- `emulation/devtest/mfc/`, `emulation/devtest/faradaycup/`, `emulation/devtest/turbo/`
Nothing else. No `st.cmd`, no port files, no Compose file, nothing in the simulator core, not `libcom1.proto`, not `libcom1_device.db`.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    emulation/sim/run_tests.sh
    emulation/devtest/run.sh emulation/devtest/mfc
    emulation/devtest/run.sh emulation/devtest/faradaycup
    emulation/devtest/run.sh emulation/devtest/turbo

All exit 0. Against simulators and a real IOC the cases cover:
- every PV is read and none is INVALID in normal operation;
- MFC: the set point is written, its read-back and the flow follow; a `NAK` ends in an alarm, a missing answer ends in an alarm; a second address on the bus does not disturb the first;
- turbo: start pump 1, see accelerating, then normal, speed and current arriving through the monitor port, `age` staying low; stop; `trip` gives failure and a MAJOR alarm, stop resets it; pump 2 is independent of pump 1; an unacknowledged start ends in an alarm; with the monitor simulator silent, `age` goes into alarm while the relay PVs stay valid, and with the Opta silent the relay PVs go INVALID while the monitor PVs stay valid;
- for every device: `silent` turns its PVs INVALID within 5 s (for the listen-only port: within the `age` limit), `clear` recovers them without an IOC restart, `close` and reopen the same;
- the IOC log contains no database, protocol or link error.

# Rules
- Do not invent protocol details and do not present an assumption as a fact. Every part of your work belongs to one of three classes, and your report says which: from a document (name it), from the lab's files, or assumed.
- Keep it small and readable.
- Leave no container running when you finish.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t5-mfc-fc-turbo @ <commit>
    BUILT: one line per deliverable
    PVS: every PV with type, unit and scan, new names marked NEW
    MACROS: every macro of each database with default and meaning, and the dbLoadRecords lines for the MFC, the Faraday cup, the Opta, both pumps and both monitor ports
    SIMULATOR SETTINGS: the configuration keys of both simulator types and the libcom1 entries for the Faraday cup and the turbo Opta, with examples
    SOURCES: which document (title, revision, URL) settled which part of the MKS protocol
    VERIFIED: the four acceptance commands with exit code and key output
    DECISIONS: choices the brief left open, each with one reason
    ASSUMED: everything no document settled, in one list per device
    NEEDS THE LEAD: changes outside your files, open questions, anything that did not work
