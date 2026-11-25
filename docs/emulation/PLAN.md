# Work plan: emulated IOCs and new RAS front end

Branch `emulated-iocs`, started from `origin/libcom1-robustness-fixes` (`99beb4f`).
The design is in [DESIGN.md](DESIGN.md), the current state in [STATUS.md](STATUS.md).

## How the work is split

- The lead (this session) plans, writes every brief, runs every acceptance test and integrates.
- Implementation goes to subagents on Opus 5.5, one git worktree per task (created by the
  Agent tool), each on its own branch `emu/<task>` cut from `emulated-iocs`.
- **No two tasks own the same file.** Device tasks do not touch `st.cmd`, the port files, the
  simulator configuration or the Compose file. They deliver databases, protocol files, a
  simulator module and a self-contained test. The lead wires them into the shared files.
- Results are merged one at a time, after the lead has run the acceptance test in the worktree.

## Gates

| Gate | Content | State |
|---|---|---|
| G0 | Startup questions | closed: zip found, `latest.zip` received, the rest on best judgement until the lab files arrive |
| G1 | Design note | closed: approved 2026-11-21, D1 to D8 as proposed |
| G2 | GUI layout proposal | closed: decided 2026-11-21, option B with device windows |

## Tasks

| Id | Task | Owns | Depends on | Acceptance test |
|---|---|---|---|---|
| T1 | IOC image, EPICS top, Compose skeleton, Channel Access proof | `emulation/docker/`, `emulation/compose.yaml`, `emulation/Makefile`, `EPICS/ioc/` (without device lines in `st.cmd`) | G1 | `make up` starts two IOC containers with one test record each. `caget` reads both from a third container and from the WSL host, using the subnet broadcast address |
| T2 | Simulator core and libcom1 simulator | `emulation/sim/mist2sim/core/`, `.../devices/libcom1.py`, `emulation/sim/tests/` | G1 | Unit tests for timing, faults and the control interface. Replay of `AVR/libcom1/tests/script.hpp` gives output identical to `replay_host` for both number formats |
| T3 | Matsusada CO bus: simulator, AU and REK databases | `devices/matsusada_co.py`, `EPICS/Db/matsusada_*`, `EPICS/Db/rek.*`, `EPICS/Db/au_alloff.db` | T1, T2 | Throwaway IOC against the simulator: all PVs read, set points followed, a silent unit turns its PVs INVALID and recovers, `AU:alloff:set` switches both chains off, rate report for 2 + 2 supplies |
| T4 | TDK and nAIM: simulators and databases | `devices/tdk_genesys.py`, `devices/edwards_naim.py`, `EPICS/Db/tdk.*`, `EPICS/Db/aim.*` | T1, T2 | Same pattern. An unanswered TDK set ends in an alarm |
| T5 | MFC, Faraday cup, NT 20: simulators and databases | `devices/mks_rs485.py`, `devices/nt20_monitor.py`, `EPICS/Db/mfc.*`, `EPICS/Db/faradaycup.db`, `EPICS/Db/turbo.db`, `EPICS/Db/nt20_monitor.*` | T1, T2 | Same pattern. The NT 20 record parser is one protocol file and one database |
| T6 | libcom1 device databases on lab names | `EPICS/Db/thermocouples.db`, `solenoidbox.db`, `pressure.db`, `sensorbox.db`, `interlockbox.db` | T1, T2 | Same pattern. An unacknowledged valve set ends in an alarm |
| T7 | Integration: both `st.cmd`, port files, simulator configuration | `EPICS/ioc/iocBoot/*/st.cmd`, `ports.*.cmd`, `emulation/sim/config/` | T3 to T6 | Both IOCs start without one database or protocol error (the IOC log is checked by a test) |
| T8 | System test suite | `emulation/tests/` | T7 | `make test`: every PV read, every set point written and followed, missing acknowledgement gives an alarm, fault injection and recovery per device, update-rate report for the AU chains |
| T9 | RAS scaffold and pvServer proof | `RAS/mist2/`, `.gitmodules` | none for the scaffold, T1 for the proof | The development GUI opens in a browser. pvServer reads one PV from each emulated IOC |
| T14 | GUI layout options | `docs/emulation/gui/` | none | Two or three wireframes with a recommendation (gate G2) |
| T10 | Plan and registry | `plan/controls.yaml`, `plan/build.py`, `plan/registry.py`, generated `RAS/mist2/.../registry.json` | T7 | `python plan/build.py` runs without warnings and shows the built PVs as existing. The registry lists every device with its PVs |
| T11 | GUI: widgets per device class, pages, alarm colors | `RAS/mist2/ReactApp/src/` | G2, T8, T10 | Every device visible, alarm state follows a fault injected in the simulator, no PV name outside the registry |
| T12 | Plant model (second step) | `emulation/sim/mist2sim/plant/` | T8 | Filament current drives discharge current with a thermal lag. Gas flow and pumps drive the pressures. Simulators unchanged |
| T13 | `docs/emulation/README.md` | that file | T8, T11 | Followed step by step on a clean clone |

## Order

```
G1 ─► T1 ─┬─► T3 ─┐
      T2 ─┼─► T4 ─┤
          ├─► T5 ─┼─► T7 ─► T8 ─┬─► T10 ─┐
          ├─► T6 ─┘             │        ├─► T11 ─► T13
     T9, T14 ─► G2 ─────────────┴────────┘
                                T12 after T8, independent of the GUI
```

T1, T2, T9 and T14 run in parallel. T3 to T6 run in parallel after T1 and T2.

## Second round: control loop and data logging (from 2026-11-22)

The owner's order: the PID loop first, then the logger. The tasks run one after the other, so
each may touch the shared files (`compose.yaml`, `plan/controls.yaml`, the test suite).

| Id | Task | Owns | Depends on | Acceptance test |
|---|---|---|---|---|
| T15 | Discharge current loop: PID as a Python service (pyepics), the loop's records and the backstop in the platform IOC, tests, plan and registry. Brief `T15-loop-ioc.md`, replaced on the same day by `T15b-loop-python.md` after the owner's decision for Python | `EPICS/Db/loop.db`, `loops/`, the emulation's shared files, `plan/`, `docs/emulation/LOOP.md` | none | Unit tests of the algorithm; `make test` with every hand-back and the backstop without the service; closed loop on the plant model at 22 A |
| T16 | GUI round: widget of the class `loop` and its place on the plasma page; set points and requests set in place in the tags of every drawing; tabs that open as windows and come back (owner's answers 23, 24); GUI check | `RAS/mist2/ReactApp/src/`, `RAS/mist2/tools/` | T15 | `gui-check.sh` passes with the loop shown and operated, a value set from a tag, a tab out and back |
| T17 | Data logger: retention tiers in the plan, generated PV list, logger service on TimescaleDB, Grafana, status records, tests | `logger/`, `EPICS/Db/logger_status.db`, `plan/`, `docs/emulation/LOGGER.md` | T15 (beside T16, the emulation shared through the lock); the owner's choice of the store (the brief assumes TimescaleDB, my recommendation, until he says otherwise) | `make -C logger test`: every tier against independently computed values, gaps, database loss, life times, status alarm |
| T16b | The logger in the GUI (Infrastructure page only, a widget, a chip in the status strip), the loop's permits by their names, the list of trends from the registry | `RAS/mist2/ReactApp/src/`, `RAS/mist2/tools/`, one line of `plan/controls.yaml` | T16, T17 | `gui-check.sh` passes with the logger running and stopped |
| T17b | Fix round of the logger after the lead's session: the loop's writes not in the event log while in PID, the right reason in a mode event, Grafana down to raw data, the loop's graphs in the dashboards, a rejected batch given up | `logger/`, `plan/` | T17 | The three acceptance commands of T17, and the lead's session repeated |
| T18 | Request records of valves, turbopumps and ion gauge take over the device's state at the first contact after an IOC start, without sending anything (open point P25) | `EPICS/Db/` (rack devices), `iocRack/st.cmd`, `emulation/tests/`, `plan/` | T17 (a tier for every PV) | Suite with the IOC restarted while devices are on; `gui-check.sh` without request records in its note |
| T17c, T17d | Two more rounds of the logger from the lead's sessions: a value that holds is returned to the end of its stretch (T17c); Grafana draws lines in a panel with several series (T17d) | `logger/` | T17b | `make -C logger test`, and the lead looks at the dashboard |
| T19 | First contact of the Matsusada and REK supplies under one hold of the lock: no gap in which a voltage set point is accepted and not sent (open point P40, ordered by the owner on 2026-11-23); every `seq` of the databases looked at | `EPICS/Db/supply_first_contact.db` (new), `EPICS/Db/matsusada_au20p7.db`, `EPICS/Db/rek.db`, the two `st.cmd` files, `emulation/tests/`, `plan/` | T18 (the pattern of `first_contact.db`) | Suite, the Matsusada device case and `gui-check.sh`; a client writing the voltage through an IOC restart ends with set point equal to the supply's echo |
| T20 | The interlock gate of the Matsusada and REK supplies keeps the output off as a state: while the permit is lost and a supply reports its output on, the off sequence is sent again (open point P45, ordered by the owner on 2026-11-23); the same race in the operator's directions reported, not changed | `EPICS/Db/matsusada_au20p7.db`, `EPICS/Db/rek.db`, `emulation/devtest/matsusada`, `emulation/tests/`, `plan/` | T19 | Suite, the Matsusada device case and `gui-check.sh`; with the door open, a direct write of `ToggleOutput` to 1 is switched off again within 4 s; a normal permit loss still sends one off sequence |
| T21 | A switching command written into `ToggleOutput` of a Matsusada or REK supply while it is busy is sent when the record is free (open point P47, ordered by the owner on 2026-11-23): internal record `_out:resend`; the lost write made on purpose in the device case | `EPICS/Db/matsusada_au20p7.db`, `EPICS/Db/rek.db`, `emulation/devtest/matsusada`, `plan/` | T20 | Suite (no new test), the Matsusada device case and `gui-check.sh`; a value written without the put flag into the busy record is sent within a second, in both directions; nothing is sent twice |
| T22 | After one late reply the requests and replies of a Matsusada or REK line are in step again after the first mismatch (`@mismatch` in the protocol files), and a reading that carries a state or a setting checks the unit number in a status reply before it trusts a reply without one (open point P49, ordered by the owner on 2026-11-23); the monitors unchanged, what that leaves measured and reported | `EPICS/Db/matsusada_co_ctrl.proto`, `EPICS/Db/rek.proto`, `emulation/devtest/matsusada` | T21 | Suite (no new test), the Matsusada device case and `gui-check.sh`; one reply made 300 ms late with two supplies at different voltages on a line: in step after one mismatch; at an IOC start a supply takes over its own state and setting although its neighbour's replies are late |
| T23 | The scan program (work package WP11, ordered by the owner on 2026-11-24): a Python program that runs a one-dimensional scan through Channel Access only, with definition files, honest data files and a clean end in every case; first use the dipole scan | `scans/`, `emulation/devtest/scan`, `docs/emulation/SCAN.md` | none | Unit tests, the device case `scan`, the plan check, once by hand in the full emulation with the plant model |
| T24 | The dipole magnet supplies as PVs: a Python service that owns the NI USB-6001 and serves it as a libcom1 device over TCP (`daq/mist2daq`, a simulated and an unverified real backend), `dipole.db`, a device case. Loaded by no IOC yet | `daq/`, `EPICS/Db/dipole.db`, `emulation/devtest/dipole`, `docs/emulation/DAQ.md` | none | Unit tests, the device case `dipole`, the plan check |
| T25 | The picoammeter of the dipole scan as PVs, built for an assumed model (Keithley 6485, A44) from its manual: protocol file, database, simulator, a device case. Loaded by no IOC yet | new files in `EPICS/Db`, a simulator module, `emulation/devtest/picoammeter`, `docs/emulation/PICOAMMETER.md` | none | The simulators' tests, the device case `picoammeter`, the plan check |
| T26 | The system brought in line with the lab's files of 2026-11-24 (`reference/lab-2026`): the source supply as `AU-20P15-1`, the Faraday cup as `FC1` with two values on a serial line, five flow meters `FLOW` in place of the sensor box, a simulated libcom1 board of protocol 1, the real port file and a rule file with the names by serial number, `LAB-SETUP.md` | `EPICS/Db/faradaycup.db`, a flow meter database, `EPICS/ioc/iocBoot/iocRack`, `EPICS/ioc/host`, `emulation/sim/config`, device cases, `plan/`, `RAS/mist2`, `logger/`, documents | none | Plan check, suite, simulators' tests, two device cases, GUI check, the logger's tests |
| T27 | The three parts of the dipole scan together: a device case in which the shipped scan program runs the dipole scan against the DAQ service and the picoammeter simulator through one IOC, with a spectrum model of the case; what the parts' numbers mean together | `emulation/devtest/dipolescan`, a section of `docs/emulation/SCAN.md`, corrections to the parts with a failing test each | T23, T24, T25 | The new case, the three cases of the parts, the simulators' tests, both sets of unit tests, the plan check |
| T28 | Firmware for an Arduino Opta in place of the lost interlock box (owner, 2026-11-24): the two door switches, the old box's four channels so that no PV and no database changes, two relays that follow the doors without the IOC, a hold time, a watchdog; a reproducible compile for the Opta and the Mega sketches in a container; tests of the decision and of the device on a PC, and the simulator's entry compared with the firmware line by line | `AVR/devices/InterlockOpta`, `AVR/tools`, the entry `interlockbox` of the simulator's configuration and of the device case | none | The three compiles, the sketch's tests on a PC, the library's tests, the simulators' tests, the device case `libcom1_devices`, the plan check; then the system tests on the merged branch |
| T29 | Read-only support for the Edwards TIC controller of the lab ("the Edwards TIC station", owner, 2026-11-25): a probe for the rack server first, protocol file and database (three gauge sockets, turbopump, backing pump, identity; pressures in torr; nothing is commanded), a simulator module, a device case, a document. Which TIC variant it is and what hangs on it is not known: brief `T29-edwards-tic.md` | `EPICS/Db/tic.*`, `EPICS/ioc/host/edwards_tic_probe.py`, the simulator module, `emulation/devtest/tic`, `docs/emulation/TIC.md` | none | The probe against a fake, the simulators' tests, the device case, the plan check; then the lead loads it into the rack IOC and runs the system tests |
| T30 | Read-only support for the INFICON VGC401 that reads the foreline gauge (owner, 2026-11-25): a probe first, protocol file and database (`FORELINE:getpressure` in torr with its state, the gauge's kind, the unit, the error state, identity), a simulator module, a device case, a document with the cable. Brief `T30-inficon-vgc401.md` | `EPICS/Db/vgc401.*`, `EPICS/ioc/host/inficon_vgc401_probe.py`, the simulator module, `emulation/devtest/vgc401`, `docs/emulation/VGC401.md` | none | As T29 |
| T31 | The owner's change of 2026-11-25 for the gauges: the homemade gauge box out of the rack IOC, the emulation and the plan; the six-way cross's pressures from the TIC (APG on socket 1, AIM on socket 2), the emulation's pressures feeding the simulated TIC and VGC401 as the real ones behave; the GUI's drawings with those gauges and the foreline gauge, a state word where a pressure is INVALID, and the title and banner fault (P68). Brief `T31-gauges-on-the-tic.md` | Rack IOC start and port files, the rule file's line, the simulator's configuration and plant coupling, the plan and registry, the system tests, the GUI's drawings and banner, `LAB-SETUP.md` | T29, T30 | Plan check, simulators' tests, the device cases, the system tests, the GUI check, the rack IOC's start with the real port file |
| T32 | Start and stop of the TIC station's backing pump and turbopump from the IOC and the GUI (owner, 2026-11-25: "yes, I want to start and stop the pumps from the GUI"): two acknowledged requests in a database of their own beside the read-only one, the read-back from the TIC's states, take-over at an IOC start without sending, two refusals for the pump's sake (no turbopump start without the backing pump, no backing pump stop under a running turbopump), the simulator executing the commands as the controller was seen to, the GUI with confirmation. Brief `T32-tic-pumps.md`. Starts when T31 is merged | The new database and protocol entries, the TIC's simulator and device case, the rack IOC's load lines, the plan, the system tests, the GUI, `TIC.md`, `LAB-SETUP.md` | T31 | As T31 |

## What every brief contains

The briefs as sent are in [briefs/](briefs/).

Goal, owned files, interfaces to respect (simulator core API, macro names, PV names from
DESIGN.md), the manual or reference files to read, the acceptance test as a command, and the
report format: what was built, what was verified and how, what was assumed, what is open.
Every brief also says: do not invent protocol details. What the manual does not say becomes a
setting with a comment and a line in the report.

## Tools on this machine

`sudo` needs a password, so nothing is installed on the host. EPICS, Python tooling, Node and
Graphviz live in containers. `plan/build.py` runs in the tools container (`make plan`).
