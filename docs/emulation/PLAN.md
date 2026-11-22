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
