You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T6: the databases of the five Arduino devices. A lead engineer wrote this brief, will run your acceptance test himself, and will merge your branch. Other engineers work in parallel on other files, so stay inside the files you own.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t6`, on branch `emu/t6-libcom1-devices`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. `/home/daniel/code/rfq-dip-epics` itself is the lead's worktree: never edit, stage or commit anything there. Check that `git -C /home/daniel/code/rfq-dip-epics/.claude/worktrees/t6 branch --show-current` prints `emu/t6-libcom1-devices`. If not, stop and report.
- Commit on that branch only. Small commits with clear messages. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo. The images `mist2-ioc:dev` and `mist2-tools:dev` exist already (`make -C emulation build` rebuilds them from cache if needed).

# Read first
1. `docs/emulation/DESIGN.md`: the approved design, sections 1 and 3.
2. `EPICS/README`: how the databases of this branch handle acknowledged sets, polling, alarms and identity. `AVR/libcom1/README.md`: the protocol.
3. `emulation/sim/README.md`: the simulator. The type `libcom1` is configured entirely in YAML, you write no simulator code. `emulation/sim/examples/` has two examples.
4. `emulation/README.md` and `emulation/devtest/example/`: the harness that runs simulators, one IOC and your tests together.
5. The databases you work on, in `EPICS/Db`: `thermocouples.db`, `solenoidbox.db`, `pressure.db`, `sensorbox.db`, `interlockbox.db`, and `libcom1_device.db` and `libcom1.proto`, which you use but do not change.
6. The lab's versions from 2023, the baseline for PV names and meaning: `reference/lab-2023/EPICS/Db/IOC.thermocouples.db`, `IOC.solenoidbox.db`, `IOC.pressure.db`, `IOC.sensorbox.db`, `IOC.interlockbox.db`, how they are loaded in `reference/lab-2023/EPICS/st.cmd` (the `DEVICE` prefixes), and the operators' labels for the channels in `reference/lab-2023/RAS/Devices.js`.
7. The firmware, which defines the channel order and the serial settings of each device: `AVR/Thermocouple/Thermocouple.ino`, `AVR/devices/SolenoidValveBox/SolenoidValveBox/SolenoidValveBox.ino`, `AVR/devices/IonGaugeController/IonGaugeController.ino`, `AVR/devices/SensorBox/SensorBox.ino`, `AVR/devices/InterlockBox/InterlockBox.ino`.

# Background
Five Arduino boards speak our own line protocol libcom1: a thermocouple board on the high-voltage platform, and in the rack a solenoid valve box, a gauge controller, a sensor box (temperatures and water flows) and an interlock box (two door switches). The databases in `EPICS/Db` on this branch are the technically better ones: acknowledged sets, identity records, and alarm propagation, so that a dead device turns its PVs INVALID. The lab's files from 2023 are older in technique but carry the PV names and meanings that the lab's clients use:

| Device | asyn port | `DEVICE` prefix in the lab | Database |
|---|---|---|---|
| Thermocouple board | `thermo` | `THM` | `thermocouples.db` |
| Solenoid valve box | `AVR12` | `VALVE` | `solenoidbox.db` |
| Gauge controller | `AVR6` | `PRESSURE` | `pressure.db` |
| Sensor box | `AVR10` | `SENSOR` | `sensorbox.db` |
| Interlock box | `AVR11` | `INTLK` | `interlockbox.db` |

The prefix is a macro already, so most names agree. Your job is to make the five databases of this branch carry the lab's names and meanings wherever the two differ, keep this branch's technique, and prove all five against the simulator.

# Files you own
- `EPICS/Db/thermocouples.db`, `EPICS/Db/solenoidbox.db`, `EPICS/Db/pressure.db`, `EPICS/Db/sensorbox.db`, `EPICS/Db/interlockbox.db`
- `emulation/devtest/libcom1_devices/` (your test case: simulator configuration for the five boards, IOC lines, tests)
Nothing else. No `st.cmd`, no port files, no Compose file, no simulator code, not `libcom1.proto`, not `libcom1_device.db`. If you need a change there, say so in your report.

# Deliverables
1. **Compare, record by record**, each of the five databases with the lab's version: record names (with the lab's prefix), record types, the meaning of the values, scan rates. Give the comparison as a table in your report. Rule: **a PV name that exists in the lab's version keeps its name and the numeric meaning of its value.** Improvements of this branch stay where they do not change name or meaning. Where the two versions contradict each other, the lab wins, and you report the case.
   - Known case: the interlock summary. The lab has `interlock_open` (1 when a door is open, with an alarm), this branch has `interlock_status`. The lab's name and meaning win. Check carefully which input value means "door closed" in the firmware, in the lab's database and in this branch's database: the comments disagree. The firmware decides, and your test proves it.
2. **Thermocouple board.** The board sends 16 channels (4 thermocouple temperatures, 4 cold-junction temperatures, 4 fault codes, 4 junction fault codes) and the database uses only the first 4. Add `$(DEVICE):j<n>:get` (junction temperature) and `$(DEVICE):f<n>:get` (fault code as a named state: no fault, no sensor chip, voltage fault, open thermocouple, with alarm severities) for n = 1 to 4. A temperature whose thermocouple is faulted must not look like a valid reading: when the firmware reports a fault, `$(DEVICE):t<n>:get` must be in alarm. Fix the description of the array record, which still says "All solenoid statuses".
3. **Units, precision and descriptions** on every value record where the firmware makes the unit certain (temperatures in degrees Celsius, pressures in torr). Where the unit is not certain (water flows), leave it empty and report it. Use the operators' labels from the lab's `Devices.js` in the descriptions where they exist (for example which valve is on which channel) only if they are the same for every instance of the database, otherwise leave descriptions generic: one database must still serve any box of its type.
4. **Identity.** Every board is loaded together with `libcom1_device.db`. The test checks name, firmware and channel list of each board.
5. **Simulator configuration** for the five boards in your test case, each matching its firmware: identity string, channel list in firmware order, readable and writable channels, baud rate and line ending as the sketch sets them, AVR number format. The lead will copy these into the configuration of the full emulator, so make them complete and comment where a value comes from. Report every disagreement between a sketch and the lab's `st.cmd` (for example baud rate or parity).

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    emulation/devtest/run.sh emulation/devtest/libcom1_devices

It exits 0. Against five simulators and one real IOC it covers:
- every PV of every board is read, with the lab's prefixes, and none is INVALID in normal operation;
- every valve channel is set and its read-back follows;
- a set that the box rejects ends in an alarm, and a set that gets no answer ends in an alarm;
- for each board separately: `silent` turns ITS PVs INVALID within 5 s and leaves the other four boards untouched, and after `clear` they recover without an IOC restart; `close` and reopen: the same; `garbage`: alarms, recovery;
- a thermocouple fault code from the simulator puts the temperature PV in alarm and shows the named fault state;
- both door switches in both positions give the right `interlock_open` and the right alarm state;
- the identity PVs;
- the IOC log contains no database, protocol or link error.

# Notes from the tasks that are already merged
- **Harness**: `emulation/devtest/run.sh <case-directory> [pytest arguments]`. The case directory holds `sim.yaml` (a YAML LIST of simulator entries), `ioc.cmd` and `test_*.py`. `ioc.cmd` may use `$(SIM_HOST)`, `$(MIST2_DB)` and `$(CASE_DIR)`. The harness loads `ioc_info.db` with `P=DEVTEST` and waits for `DEVTEST:heartbeat`. An error in `ioc.cmd` stops the IOC, and the harness then prints the log tails and exits 99. Logs are in `<case-directory>/build/`. Do not run the same case directory twice at the same time.
- **Simulator core**: `emulation/sim/README.md` is the reference. Tests reach the control port with `mist2sim.control.ControlClient`. `get` returns values without noise. A silent unit does not execute what it is sent.
- **Startup files**: an error inside a file loaded with `iocshLoad` does not stop the IOC unless that file starts with `on error break`. The harness adds the line for `ioc.cmd`.
- **Temporary files**: make your own directory with `mktemp -d`. Do not use a shared scratch directory: other engineers write there at the same time.
- **Docker**: three other engineers run their own test cases on this Docker daemon at the same time. Touch only containers and networks of your own runs. Do not rebuild the images unless a file under `EPICS/ioc` or `emulation/docker` changed, and you must not change those.
- **Load**: the unit-test suite contains timing tests with real sockets. If one fails once while the machine is busy and passes when repeated, say so in your report and do not loosen it.

# Rules
- Do not invent facts. The firmware and the lab's files decide. What they do not say goes into your report as an open point.
- Keep it small. No new PV names beyond those listed above.
- Leave no container running when you finish.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t6-libcom1-devices @ <commit>
    COMPARISON: the record-by-record table, lab 2023 against this branch, and what you did in each differing case
    PVS: every PV per board (with the lab prefix) with type, unit and scan, new names marked NEW
    DBLOADRECORDS: the lines for the five boards, each with its libcom1_device.db line
    SIMULATOR CONFIGURATION: the five entries
    DISAGREEMENTS: firmware against lab st.cmd against databases
    VERIFIED: the acceptance command with exit code and key output
    DECISIONS: choices the brief left open, each with one reason
    NEEDS THE LEAD: changes outside your files, open questions, anything that did not work
