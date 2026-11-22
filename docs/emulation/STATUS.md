# Status

Last update: 2026-11-22. The gates G0, G1 and G2 are closed. Branch `emulated-iocs` is local,
nothing is pushed.

Everything is built and merged. The system suite and the GUI check pass on the final state.
Nothing is running.

A second round is running: the PID loop, then the logger (see "Running").

Added after that (2026-11-22), outside the task's scope, when you pointed to Matsusada's driver
CD and your notes: the Linux side of the CO-U32, a udev rule and a read-only probe. Not tested
on hardware. Data logging, the control loops and the PDF printout are not built: the task
named them as later additions.

## "Done" as the task defines it

| # | Criterion | State | Evidence |
|---|---|---|---|
| 1 | `docs/emulation/README.md` explains start, stop and test | Done | Every command of it was run by the lead, the two fault one-liners on 2026-11-22. Not tried on a fresh WSL installation |
| 2 | Both IOCs start without a database or protocol error | Done | `make -C emulation up` and `ca-proof` (16 checks) on the merged tree. No connection complaint in either IOC log after start and after restart |
| 3 | A test reads every PV, writes every set point, and an unacknowledged set ends in an alarm | Done | `make -C emulation test`, run twice from nothing by the lead on the final state: 220 passed, no expected failure, 8 min 47 s each, nothing left running, saved limits unchanged |
| 4 | A silent simulator turns its PVs INVALID within seconds, recovery without IOC restart | Done | The same runs: every fault on every simulator, with all other devices unaffected and recovery without an IOC restart. By hand: TDK silent, INVALID within 6 s, valid again 6 s after clearing |
| 5 | AU update rate reported and matching the bus arithmetic | Done | The same runs: all four AU supplies 9.19 Hz against 9.80 Hz predicted (94 %), TDK 9.99 Hz against 10.00 Hz. Table in `emulation/build/update-rate.md` after a run |
| 6 | The GUI runs against the emulator, shows every device, reflects the alarm state | Done | `gui-check.sh`, run three times in a row from nothing by the lead on the final state: 199 of 199 checks each time, 275 displayed values equal to Channel Access, no console error or warning. The console error of the run before is fixed at its cause (see "GUI") |
| 7 | `plan/controls.yaml` matches what was built, `plan/build.py` runs without warnings | Done | Revision 0.10. `make -C emulation plan-check` passes on the merged tree, the registry regenerates without a difference |
| 8 | This file lists every assumption that needs confirmation | Done | Sections "Assumptions" and "Open points" |

## Done

**Emulated IOCs**
- Image `mist2-ioc:dev`: EPICS base R7.0.10, asyn R4-46, StreamDevice 2.8.26, autosave R5-11,
  all unmodified release tags, and the EPICS top `EPICS/ioc`.
- One `st.cmd` per IOC, the same for emulation and reality. Only `ports.sim.cmd` and
  `ports.real.cmd` differ. An IOC without a valid mode stops instead of starting.
- `emulation/compose.yaml`: rack IOC `172.30.0.11`, platform IOC `.12`, their simulators `.21`
  and `.22`, plant model `.30` on request. `make -C emulation build up ca-proof restart down`.
- Channel Access proof, 16 checks: both IOCs answer a broadcast from the bridge network and
  from the WSL host, and each answers a unicast search for its own PVs only.
- Start order (2026-11-22): the IOCs start only after their simulators listen. `restart`
  restarts the two IOCs and leaves the simulators and their state alone. Before, a restart
  could leave a Matsusada chain unreachable for 20 s (found by the lead by hand).

**Devices: databases, protocol files, simulators** (each with a test case run by the lead)
- Matsusada AU and REK (`matsusada_au20p7.db`, `rek.db`, `au_alloff.db`), reworked after your
  answers. The device case passed 28 of 28 in five runs in a row.
  - Four AU supplies: units 1 and 2 on the USB-OPT chain, 3 and 4 on the CO-U32 chain.
  - The permit latches: losing `interlock_open` switches the output off and clears the request.
  - `<supply>:current:limit` is a PV of its own, with the lab's name `current:setpoint` as an
    alias. It is restored at IOC start from `EPICS/ioc/iocBoot/<ioc>/limits.defaults` and then
    from the file saved at run time, which wins. It is sent at the first contact, on every
    write and with every switch-on. A change is saved within 5 s.
  - Remote mode (`REN`) is sent at the first contact and with every switching only.
    `status:read` shows local control (`OFF, LOCAL`, `ON, LOCAL`, MINOR).
  - First contact: the IOC takes over the output state and the voltage set point of a supply
    without sending anything, also when the supply is reached only later.
  - Each supply reads its two monitors as one cycle and waits its turn on the line, so all
    supplies of a chain update at the same rate.
- TDK GENESYS (`tdk.db`): all sets acknowledged, new PVs `TDK:power:get`, `TDK:mode:get`,
  `TDK:fault:get`. 13 tests.
- Edwards nAIM (`aim.db`): 11 tests. MKS mass flow controller (`mfc.db`, new `MFC:getFlow`): 9
  tests, protocol from the vendor's RS-485 supplement.
- Faraday cup (`faradaycup.db`): 6 tests. Turbopumps (`turbo.db`, `turbo_pump.db`,
  `nt20_monitor.db`): 10 tests.
- libcom1 devices (`thermocouples.db`, `solenoidbox.db`, `pressure.db`, `sensorbox.db`,
  `interlockbox.db`): 82 tests. New PVs `THM:j<n>:get`, `THM:f<n>:get`.
- Simulator core `mist2sim`: baud-rate-true reply delay, signals, faults `silent`, `close`,
  `garbage`, `slow`, `trip`, one control interface for all. 129 unit tests. The libcom1
  simulator gives the same 122-line transcript as the real library, in both number formats.

**System tests** (`make -C emulation test`, see `emulation/tests/README.md`)
- 220 tests, generated from the registry wherever possible: start without an error or a
  connection complaint, every PV read, every set point written and followed, sets without
  acknowledgement, every fault on every simulator with recovery, the latch across both IOCs,
  the limit sent with every switch-on, local control from the front panel, update rates, and a
  clean end. Run twice by the lead on the final state: 220 passed both times, about 9 minutes.
- The suite restores every current limit it writes. The saved limits were the same before and
  after the two runs.

**Plan and registry**
- `plan/controls.yaml` revision 0.10 describes what is built, with your answers in it.
  `make -C emulation plan-check` compares it with `EPICS/Db` and both `st.cmd` and fails on any
  difference.
- Registry `RAS/mist2/ReactApp/src/registry/registry.json`, generated from the same sources:
  18 devices, 2 IOCs, 279 PVs, 15 simulators. It carries roles, read-backs, safe test ranges,
  state words, the vent valve confirmation, spare channels, aliases, and which simulator fault
  turns which PV INVALID.

**GUI** (`RAS/mist2/`, React Automation Studio V8.1.0 as a submodule)
- Layout B on the phase 1 arrangement: overview drawing, one tab per subsystem, every device in
  a browser window of its own. Dark theme, no login, confirmation only for opening the vent
  valve. Every device, PV name and word comes from the registry.
- `RAS/mist2/tools/gui-check.sh`: headless browser checks, 199 in all. They compare 275
  displayed values with Channel Access, silence a device, stop an IOC, write set points, and
  prove the latch and the vent valve confirmation in the GUI.
- Values are formatted by unit: exponent form for pressures, a prefix for small currents and
  large voltages with the record's resolution (1.001 µA, 15.234 kV).
- The console error "Maximum update depth exceeded" (one failed check on 2026-11-22) is fixed.
  The subagent reproduced it on 11 of 30 loads (load, open a device window, reload) and on
  none of 50 after the fix. Cause: the RAS components `Widget`/`PV` and `GraphY` set React
  state in effects on every value, and with all pages mounted React's count of such updates
  never returned to zero. Read-backs now use the RAS socket hook directly, and trends are
  drawn by a component of our own (`Trend.jsx`, Plotly). RAS `Widget` stays for the fields
  that write.
- Trends (changed by the lead after the merge, each point seen in a browser test): a line is
  drawn in steps and runs on to the present, so a value that does not change is a line and not
  one dot. A line ends where its record turns INVALID or the connection is lost, and starts
  again with the next valid value. A trend without any valid value says so. A zoom stays
  until a double click; before, the redraw undid it within a second.
- With an IOC stopped or a device silent, the tab dots of a freshly opened window are right
  after 1 s (noted by the check in every run).

**Plant model** (`make -C emulation up-plant`)
- Filament, discharge, gas and vacuum, extraction, heat. Calibrated to your working point,
  pumping speed from the TURBOVAC 1000 C data sheet.
- Checked by the lead on the full emulation (2026-11-22): the pump runs up in about 70 s and
  the pressure falls; with gas, filament and discharge on, the discharge current, the nAIM
  reading (7.0e-6 torr), the Faraday cup current (3.4 mA with the cup in, nothing with it out)
  and the back plate temperature respond; 80 A instead of 90 A on the filament takes the
  discharge from the supply's limit to 4 A; closing the gas valve ends it. After `plant-stop`
  every device is back on its own behaviour.

**Matsusada CO-U32 on Linux** (`EPICS/ioc/host/`, by the lead, 2026-11-22)
- Found: the CO-U32 holds an FTDI USB-serial chip under Matsusada's own USB ID `1192:1000`.
  Sources: the INF files of Matsusada's driver CD rev. 1.7.0, which are FTDI's driver 2.08.28
  with that ID, and your notes of about 2016, in which you opened the adapter under that ID on
  a Raspberry Pi. The Linux driver `ftdi_sio` does not list the ID (kernel mainline of
  2026-11-22). That is why the adapter gets no serial port by itself.
- No new driver is needed: one udev rule names the ID to `ftdi_sio`, and the adapter is a
  serial device that asyn opens as on Windows. No D2XX library, no root rights at run time.
- `99-mist2-matsusada.rules`: that rule, ModemManager kept off the line, and the name
  `/dev/mist2/co-u32` for the adapter with the serial number `CO001144` (from your notes).
  It passes `udevadm verify` (systemd 255); a copy with a wrong operator fails it.
- `matsusada_probe.py`: read-only first contact (STS, SW?, CH0?, CH1?, MN1, MN2; no set, no
  REN), prints every reply, its time and whether it has the form the protocol file expects.
  Run by the lead against the Matsusada simulator through a pseudo serial port: two units
  answer (exit code 0, median reply time 24 ms), an absent unit and garbage replies are
  reported (exit code 1), a missing device ends with a message (exit code 2).
- Matsusada's current driver package (rev. 2.12.36.20, which you downloaded on 2026-11-22) is
  still FTDI's driver and names the same single ID, `1192:1000`. It does not name the
  USB-OPT. If it is the USB-OPT's driver, as you believe, the USB-OPT reports that ID and the
  rule covers it; only its serial number is missing for the name `/dev/mist2/usb-opt`.
- Install and the five check steps with the adapter: `EPICS/ioc/host/README.md`.

## Running

Second round, ordered by you on 2026-11-22: the PID loop, then the logger (work plan:
`PLAN.md`, tasks T15 to T17).

- T15, the discharge current loop: the subagent (Opus 5.5, worktree `.claude/worktrees/t15`)
  reported a Python service with the loop's records in the platform IOC, as you decided
  (answer 21, `briefs/T15b-loop-python.md`). Not merged yet. What I checked myself on its branch
  at `3a357de`: the five acceptance commands (13 unit tests, the build, 261 system tests in
  636 s, the closed-loop test on the plant model, the plan check; nothing left running), and by
  hand on the emulation with the plant: the source to 20 A in MANUAL, MANUAL to PID without a
  bump, 22 A reached in about 8 s; a write of the operator to the TDK set point, a killed
  service, a stopped service, a restart, a refused request: all hand back or refuse with the
  right reason.
- The same hand session found two defects of the loop and one of the discharge supply, sent
  back with four smaller points (seven in all). The subagent fixed them (branch at `eed9a2e`),
  and I checked each one myself: the five acceptance commands again (24 unit tests, 269 system
  tests in 703 s, the closed-loop test, the plan check) and by hand on the plant.
  1. A limit changed in PID below the present filament current left the filament current where
     it was. Now it follows to the new limit at the slew rate.
  2. With the rack IOC stopped, the loop's interlock condition kept reading "fulfilled" and the
     loop stayed in PID. Now: "no data" and MANUAL 0.3 s after a stop, about 8 s after the rack
     IOC goes silent without closing its connection (`docker pause`). The cause is in EPICS
     base 7.0.10: a record is not processed when its CP link disconnects (`dbCa.c`,
     `dbCaTask`), and a calc record keeps its last value when an input link fails.
  3. **The discharge supply, not the loop (open point P35):** with the rack IOC stopped the REK
     output stayed on although its request was cleared. Now it is off 0.1 s after a stop and
     about 8 s after a silent rack IOC, and nothing comes back when the rack IOC returns.
     `rek.db` and `matsusada_au20p7.db` got the same change.
  4. Smaller: the permit records carry no alarm while a supply is simply off and read as words;
     role names that collided with the GUI's are renamed; the set point limits are records
     (`LOOP-DIS:spmin:setpoint`, `spmax:setpoint`); the service counts a cycle only when it
     completed.
- **Still open before the merge (second fix round, running):** with a large error the loop goes
  to PID and does nothing. Seen by hand with the default settings: MANUAL at 18 A, set point
  22 A, then PID: the output stands still, flag "free", for as long as I watched. The
  anti-windup at the slew limit takes the whole integral step back when it is larger than the
  slew room (threshold: Ki times the error above the slew rate), and the tests only stepped by
  2 A, just under it. Also: a run left the slew setting at 0.5 A/s instead of 1 in the
  emulation's saved settings.
- T16, the GUI round (`briefs/T16-loop-gui.md`: the loop's widget, values set in place on the
  drawings, tabs as windows; your answers 23 and 24), and T17, the logger
  (`briefs/T17-logger.md`), start when the loop is merged. They run side by side in two
  worktrees and share the emulation through the lock `/tmp/mist2emu.lock`.
- The logger is built on TimescaleDB, my recommendation, unless you answer question 9 otherwise
  before it starts.

## Open

- Turbopump 2 is not in the system in phase 1. Its records, simulator and tests stay, and the
  plan flags it as not installed, so the GUI does not draw it. Say so if the rack IOC should
  not load it at all.
- Two gauges you want to add are in the plan as planned devices only: foreline, gas injection.
- The dipole second cross, the emittance scanners and the new interlock system are out of scope.
- Worktrees and branches of the subagents (`emu/t*`) are still there. They go when you have
  looked at the result.

## Answers of the owner, 2026-11-21

| # | Question | Answer | State |
|---|---|---|---|
| 1 | Where the gauges sit | nAIM and APG side by side on a side flange of the six-way cross. The AIM of the homemade controller goes to the second six-way behind the dipole in phase 2. The foreline has a gauge that is not in the control system yet and should be added. A pressure measurement on the gas injection is wanted too | In plan, GUI drawing and plant model |
| 2 | Valve channels, vent valve | 1 foreline, 2 MFC shutoff, 3 vent, 4 Faraday cup, 5 to 8 unused. The vent valve vents the turbopump through its side port, and the cross only a little | In plan, registry (words, spare) and plant model |
| 3 | Turbopump 2 until it exists | Keep its records, hide it in the GUI | Done |
| 4 | Thermocouples | 1 back plate, 2 filament feedthrough, 3 isolation transformer 1, 4 isolation transformer 2 | Done |
| 5 | Cooling water | The Opta flow readout replaces the sensor box | Sensor box kept as a stand-in, flagged as assumed |
| 6 | Confirmation dialogs | Only before opening the vent valve. HV is interlocked anyway | In registry and GUI |
| 7 | Theme | Dark | Done |
| 8 | Login | None, everyone may operate and open expert views | Done |
| 9 | Outputs after the interlock closes again | Latch: stay off, switch on again by hand | Done in the databases, seen by hand on the full system |
| 10 | Current limit of AU and REK | A PV of its own, not a set point. Limits are read from a defaults file at start, can be changed from the GUI, and the change is saved | Done in the databases (my reading: A27). GUI follow-up running |
| 11 | Remote mode (REN) | Only at IOC start and on switching, as in the lab | Done |
| 12 | AU supplies | Four, not five: 1 source and 2 puller on USB-OPT, 3 lens 1 and 4 lens 2 on CO-U32. Lens 3 is grounded mechanically, the fifth supply is not on the chain | Done |
| 13 | Gauge controller board | Teensy | Done |
| 14 | nAIM unit | torr | No change needed |
| 15 | Turbopump | RS-232 port fitted. "A big one", probably a TURBOVAC 1000 C with a DN 250 ISO-K flange | In plan, simulator (600 Hz) and plant model |
| 16 | Mass flow controller | 5 sccm full scale, hydrogen | Done |
| 17 | Old interlock box | In use, its two relays switch nothing | Done |
| 18 | Working point | Filament 8 V and 90 A, discharge 150 V and 24 A, about 1e-5 torr in the cross (later: maybe nearer 5e-5 torr), MFC at about 20 % of 5 sccm | Plant model calibrated to it |
| 19 | nAIM calibration (2026-11-22) | "I believe the nAIM is calibrated for N2" | Noted in the plan as your belief. It is what the plant model assumes |
| 20 | Set point of the discharge current loop (2026-11-22) | "set point below 24 A for now. 22 oughta do it." | Passed to the loop task T15: default set point 22 A |
| 21 | Where the PID runs (2026-11-22) | "Could we just use PyEPICS and run the PID in python", then chosen from three variants: Python service, the loop's records in the platform IOC | Brief T15b. The plan document said "soft IOC": the subagent brings it to this decision |
| 22 | Operating system of the platform mini PC (2026-11-22) | "one of the light ubuntu variants, I don't recall which one" | Passed to T15: the loop service's installation is written for Ubuntu. Variant and version still open (A22) |
| 23 | Setting values on the drawings (2026-11-22) | "On the main screen/tabs, all the PVs are read-only. Only if I click on it and the pop-up appears can I change a value. I would like to be able to set values in place on the main screen." | Changes the decision of gate G2 (the drawing was read-only). In brief T16 as requirement R10: set points and requests in the tags, saved settings stay in the device window, the vent valve still asks first |
| 24 | Tabs as windows (2026-11-22) | "Would it be possible to pop out individual tabs as separate windows and re-attach them if the user wants to?" | Yes, as browser windows opened by a control on the tab (a browser cannot dock). In brief T16 as requirement R11 |
| 25 | Comments on the drawings (2026-11-22) | "The filament should be vertically centered, attached to the left wall of the plasma chamber and have its tip point to the right. Stuff like that. I have a number of them." | The geometry is data (`RAS/mist2/ReactApp/src/config/drawings.json`). I apply them myself after T16 is merged: your list first, then a session with the GUI open in your browser |

## What the working point implies (from the plant model, for you to check)

- **The discharge supply is at its limit.** 24 A is the full scale of the REK150-24. At the
  working point the model sits at the edge of constant-current operation, so a discharge current
  loop through the filament current can only act downward there (model: gain 3.6 A/A for a step
  down, 0.007 A/A for a step up). Either the loop runs at a set point below 24 A, or it waits
  for the REK150-55. Your answer (20): 22 A for now.
- **The predicted pressure is below your range.** With the data sheet speed of the TURBOVAC
  1000 C (1150 l/s for nitrogen, about 1170 l/s estimated for hydrogen) and 1 sccm of hydrogen,
  the model predicts 7.0e-6 torr on the nAIM. Your range is 1e-5 to 5e-5 torr, a factor 1.4 to 7
  higher. The gauge calibration does not explain it, if the nAIM is calibrated for nitrogen as
  you believe. Remaining candidates: the gauge sits on a side flange away from the pump;
  something between the cross and the pump lowers the effective speed (valve, reducer, screen);
  the flow was higher than 20 %; the pump is a smaller one.
- The model's filament: 720 W, 2820 K, 6.7 cm2 of tungsten (a wire of about 1.4 mm by 16 cm).

## Questions for you

1. Is there anything between the six-way cross and the turbopump (valve, reducer, screen)?
2. The real current limits of the four AU supplies and the REK. The defaults files hold the full
   scales (A23).
3. Answered on 2026-11-22: the discharge current loop runs at 22 A for now (answer 20).
4. `status:read` of the AU and REK supplies is now a multi-state record (P27). Does a script of
   yours depend on its type?
5. The emulation's saved REK limit is 20 A, not the default 24 A (P30). Did you set it from the
   GUI on 2026-11-21? If not, something wrote it that I have not found.
6. The lab files (databases, protocol files, both `st.cmd`, `dbl` of both IOCs) settle A1, A4,
   A7 to A12 and A22.
7. Two defects of React Automation Studio V8.1.0 are behind the GUI's console error (see
   "Found in RAS V8.1.0"). Do you want them reported to the RAS project? I have contacted
   nobody.
8. Is the CO-U32 in the rack the adapter of your notes, serial number `CO001144` (A29)? And
   what are the USB ID and the serial number of the USB-OPT (P34)? One PowerShell command on
   the rack PC shows all of it without changing anything: `EPICS/ioc/host/README.md`, "Read
   the IDs and serial numbers on the Windows IOC".
9. The logger (WP9): a time-series database (TimescaleDB) behind a small Channel Access
   logger of our own, or the EPICS Archiver Appliance? My recommendation is the first: its
   retention and down-sampling rules are the three tiers of the plan as they stand (mean,
   minimum and maximum per second and per minute, each with its own life time), and the
   history is one SQL query away from Python. The Archiver Appliance is the community
   standard and RAS has a viewer for it, but it reduces data with one operator per store, and
   it is more to install. Without an answer I build the first when the loop is merged.

## Not verified

- The steps of `docs/emulation/README.md` on a fresh WSL2 installation: Docker was already
  installed on the machine used.
- Anything against real hardware, including `ports.real.cmd` and `run-ioc.sh ... real` on a real
  Linux computer, and autosave's directory `~/.local/state/mist2` there.
- The GUI in a browser on Windows by a person. It was checked with a headless browser inside
  WSL and by looking at screenshots. You opened it yourself on 2026-11-21, on a checkout that
  was in the middle of a merge.
- The `git clone` step of the README works only after a push.
- The udev rule and the probe of `EPICS/ioc/host/` with the real adapter. The rule was checked
  for its syntax only: whether `ftdi_sio` takes the adapter and `/dev/mist2/co-u32` appears
  can only be seen with the adapter plugged in.
- The GUI over hours. The checks keep a window open for a minute at most. Each trend line
  keeps its last 3000 values, which is 5 minutes of a value that changes ten times a second.

## Subagents

- All subagents report the model ID `claude-opus-5-5`.
- The Agent tool's own worktree isolation cuts worktrees from `master`, not from the current
  branch. The lead creates each worktree from `emulated-iocs` under `.claude/worktrees/<task>`
  (ignored by git) and names it in the brief (`briefs/`).
- A subagent's experiment script from the first hours kept starting a stray IOC container
  (`docker run` without a terminal never ends). Stopped on 2026-11-22.

## Decisions taken, with reasons

| Decision | Reason |
|---|---|
| `plan/` committed in two commits: sources, then `out/` | `out/` is 10 MB of generated files. A separate commit is easy to drop before the first push |
| `latest.zip` committed as `reference/lab-2023/`, not merged into `EPICS/Db` | It is a 2023 state and the lab has moved on. The merge into `EPICS/Db` happened per device with a visible diff |
| `plan/build.py` and all tooling run in containers | `sudo` needs a password, and Graphviz, python-docx and pytest are not installed on the host |
| Simulators in their own containers | See DESIGN.md section 2 |
| EPICS base R7.0.10, not R7.0.11 | StreamDevice 2.8.26, the latest release, does not build against R7.0.11. With R7.0.10 everything is an unmodified release tag |
| Each port file starts with the line `on error break` | Without it an error inside a file loaded with `iocshLoad` is ignored and the IOC starts half-configured |
| An IOC with an unset or wrong `MIST2_PORTS` exits instead of starting | A real computer must never come up on simulator ports by accident, or the other way round |
| The limits are saved with autosave, not with a script of our own | It is the standard EPICS module for this, it writes atomically and keeps backups. The defaults file has autosave's format, so one mechanism restores both |
| Saved limits live outside the repository (`mist2emu-save` volume, `$MIST2_SAVE/<ioc>` on a real computer) | A file that the IOC rewrites must not be a tracked file |
| IOC containers wait for healthy simulator containers; `restart` restarts the IOCs only | asyn retries a failed first connection only after 20 s. An IOC restart with the devices still running is also the case that matters on the real machine |
| Read-backs and trends of the GUI do not use RAS `Widget` and `GraphY` | Both set React state in effects on every value. With every page mounted that ends in React's "Maximum update depth exceeded". The RAS submodule stays unmodified |
| Trend lines are steps that end at INVALID and at a lost connection | A monitor sends a value when it changes. A straight line between two values, or a line through a time without valid data, would show a measurement that was not made |
| Subagents share the one emulation through a lock file | The Compose project uses fixed names and a fixed network, so only one copy can run |
| The CO-U32 on Linux through the kernel's FTDI driver and a udev rule, not through FTDI's D2XX library | The chip is a standard FTDI part under a vendor ID. With the kernel driver the adapter is a plain serial device: asyn, the protocol file and `ports.real.cmd` stay as they are, and nothing runs with root rights |
| The PID runs in a Python service, the loop's records in the platform IOC (your decision, answer 21). The IOC records also enforce output limits, slew limit, "write only in PID" and "manual when the service stops" | The loop acts on a time scale of a second, your group changes Python and not C, and the later steps are Python. The backstop in the IOC covers what that choice costs: an algorithm in a process that can stop or misbehave |

## Assumptions that need your confirmation

"Lab files" means the current databases, protocol files, both `st.cmd` and `dbl` output from
both IOCs, expected in the week of 2026-11-23. Settled by your answers and removed from this
table: A2, A3 (AU units and chains), A14 (valve channels), A18 (sensor box, old interlock box),
A19 (the output gate is wanted, and it latches).

| # | Assumption | Source | Settled by |
|---|---|---|---|
| A1 | The lab's PV names are those of the 2023 snapshot | `latest.zip`, lab GUI | Lab files |
| A4 | AU20P15: 20 kV and 15 mA full scale, same 16-bit set and 12-bit monitor scaling as the P7.5 | Model name. The local scaling fix is not in `latest.zip` | Lab files |
| A5 | Negative supplies show positive numbers | 2023 database has no sign handling | You (D3) |
| A6 | Turnaround time of the Matsusada adapters: 5 ms in the simulator | Not in the manual | Measurement on hardware |
| A7 | REK150-24 on its own port, unit 1, 9600 baud | Repository `st.cmd` | Lab files |
| A8 | TDK at address 6, 19200 baud | `tdk.proto`, repository `st.cmd` | Lab files |
| A9 | Thermocouple board at 19200 baud | Firmware says 19200, both `st.cmd` say 9600 | Lab files |
| A10 | Gauge controller (Teensy) at 115200 baud. The real port file sets even parity as the lab's `st.cmd` did | Firmware, lab `st.cmd` | Lab files |
| A11 | MFC at address 254, 9600 baud. The snapshot's files are a draft: set point only, no flow read-back, commented out in `st.cmd` | `latest.zip` | Lab files |
| A12 | `MFC:getFlow` as the name of the flow read-back | My proposal in the lab's style | Lab files |
| A13 | Faraday cup Opta speaks libcom1 over TCP and serves one current channel | Nothing: the firmware is not known | Firmware source |
| A15 | nAIM answers `!C752` as in the Edwards manual | INFICON's description of the protocol | The gauge |
| A16 | One Opta drives both NT 20, wired as "ON/OFF switch" (Fig. 6) | Manual | You, rear panels |
| A17 | NT 20 RS-232 record format is unknown. Simulator and parser use an invented format | Manual: "more details on request" | A capture from a unit |
| A20 | Emulation subnet `172.30.0.0/24` | Free choice | You, if it collides with a network of yours |
| A21 | Linux device names in `ports.real.cmd` are placeholders (`/dev/mist2/<name>`) | Only `/dev/mist2/co-u32` has a udev rule, not tested (`EPICS/ioc/host/`). The others do not exist yet | Work package WP4 |
| A22 | The platform IOC runs the same EPICS top as the rack IOC | Its `st.cmd` is unknown. Its operating system is a light Ubuntu variant (your answer 22), variant and version unknown, so the Python version there is unknown too | Lab files, and `lsb_release -a` on the mini PC |
| A23 | The defaults of the current limits are the full scales: 15, 7.5, 7.5, 7.5 mA and 24 A | No source for the real limits | You |
| A24 | A Matsusada supply in local control still answers queries (status, monitors) | The CO manual does not say | Hardware |
| A25 | The turbopump is a TURBOVAC 1000 C with a DN 250 ISO-K inlet. Its hydrogen speed is estimated from the neighbouring model in the data sheet | Your "I think", Leybold GA 05.118/14.02 | The pump's type plate |
| A26 | The nAIM is calibrated for nitrogen | Your "I believe" | The gauge |
| A27 | My reading of your answer 10: the limit PV is `current:limit`, the lab's name stays as an alias, the defaults file is `limits.defaults` per IOC, and a change from the GUI is saved to a second file that overrides the defaults at the next start. The defaults file itself is not rewritten | Your answer, autosave's way of working | You |
| A28 | The turbopump reaches its speed in 60 s in the simulator. The data sheet says about 9 minutes | Free choice, so that a desk session does not wait | Say so if you want the real time |
| A29 | The CO-U32 in the rack is the adapter of your notes of about 2016: serial number `CO001144`, USB ID `1192:1000` | Your notes, and Matsusada's driver CD rev. 1.7.0 for the ID | `lsusb -v` with the adapter plugged in |

## Open points

Closed by your answers or by later work and removed from this table: P1, P2, P4, P8, P16, P17,
P18, P19, P20, P22.

| # | Point | Needs |
|---|---|---|
| P3 | Unit of the sensor box water flows. The sketch's factor 0.06 fits litres per hour by one comment and not litres per minute by the other. The unit field is empty. The seven temperatures have no names in any source | Nothing, if the Opta replaces the box |
| P5 | The door PVs `INTLK:i1:get_interlock` and `i2` are binary records with the states Open and Closed. The lab's were analog records with the same numbers (1 = closed) | You, if a script depends on the type |
| P6 | The gauge controller keeps sending the last pressure after a gauge is switched off | Firmware, later |
| P7 | The nAIM instruction manual was not found. Its protocol is taken from INFICON's description of the "Edwards nAIM protocol" and from the Edwards TIC manual | You, with the gauge |
| P9 | `AIM:getpressure` is INVALID while the gauge is off or striking. It keeps the number the gauge sent | Tell me if you prefer another display |
| P10 | After a TDK power cycle the supply comes back with its output off, while `TDK:status:setpoint` still shows ON until it is written again. `TDK:status:get` shows the truth | GUI and loop design |
| P11 | MFC: the supplement does not show the reply to a set or a literal example of a negative reply. The protocol file accepts both forms of the positive reply | Lab files |
| P12 | Faraday cup: everything but the hardware is assumed (libcom1 over TCP, one channel in A) | Firmware source |
| P13 | Turbopump Opta: its firmware does not exist. The channel map in `turbo.db` is its specification | Firmware, later |
| P14 | NT 20 monitor port: the record format is invented. `TURBO<n>:raw:get` and `:age:get` work with any one-line format | A capture from a unit |
| P15 | The simulator's `close` fault accepts and closes every reconnect, which makes an IOC with `@init` handlers log about 100 lines per second while the fault lasts. Better: stop listening | Later |
| P21 | Simulator core, wishes from the device tasks: several input terminators, line settings changeable at run time, transaction counts per command | Later |
| P23 | `make -C emulation plan` changes the tracked PDFs on every run, because Graphviz embeds the build time. PDFs that differ only by the time stamp are left as they are by hand | Later, if it annoys |
| P24 | A supply that does not answer gets the same share of the line as a healthy one, and each of its polls costs the reply timeout (200 ms). Its neighbour on the chain drops to 1.4 Hz until it answers again | Later, if wanted |
| P25 | Set records without a first value start as INVALID (undefined) until they are written once: `VALVE:s<n>:set`, `TURBO<n>:start:set`, `AIM:enable`. Writing an initial value at IOC start is not an option (it would close the foreline valve). The clean way is to take over the device's state at the first contact, as the Matsusada databases now do | Later |
| P26 | The RAS pvServer was seen giving a long text (`TURBO<n>:raw:get` through `VAL$`) a time stamp that did not belong to that text. The GUI check tolerates it. Not investigated | Later |
| P27 | `status:read` of the AU and REK supplies is a multi-state record now. 0 OFF and 1 ON as before, 2 and 3 are new (local control). A client that reads the number sees no difference in remote mode | You, if a script depends on the type |
| P28 | A client that writes `<supply>:ToggleOutput` directly bypasses the permit, the remote command and the limit. In the lab's database it bypassed the permit too. The operator's PV is `SetToggleOutput` | Access security, later |
| P29 | After an IOC start a supply ignores a switch request until 5 s after its first answer. A request written earlier is overwritten by the state the supply reports | Know it |
| P30 | The emulation's saved limit of the REK is 20 A, not the default 24 A. I did not write it, and no test writes that value | You |
| P31 | Seen once by the test subagent, not proven: a client that reads about 200 PVs every 0.1 s from the rack IOC made Matsusada monitors INVALID for a moment. Not at idle, and gone when the suite read less | Watch for it with the real GUI and archiver |
| P32 | The system suite takes about 9 minutes. The limit set for it was 10 | Later, if it grows |
| P33 | A trend takes the time of a value from the IOC and the present from the browser's computer. With clocks that differ, the end of each line is drawn too long or not at all | Synchronised clocks (NTP) on the IOC computers and the operator's computer |
| P34 | The USB-OPT has no device name: its serial number is not known, and its USB ID is known only if Matsusada's current driver package (one ID, `1192:1000`) is its driver. No package names the USB-OPT | The PowerShell command in `EPICS/ioc/host/README.md` on the rack PC, or `lsusb` |
| P35 | With the rack IOC stopped the REK output stays on although its request is cleared, and is switched off only when the rack IOC returns. Found by hand on 2026-11-22 while checking the loop; the hardware interlock does not depend on it. Cause: a calc record keeps its last value when its permit link fails (EPICS base 7.0.10) | Fixed on the loop's branch (not merged yet) and checked by me by hand: off 0.1 s after a stop, about 8 s after a silent rack IOC; system tests `test_10_lost_permit.py` |

## Found in RAS V8.1.0

- No RAS component colours severity INVALID. The GUI has its own fields for this.
- `Widget` with `PV` hands every value on through three effects that each set state, and
  `GraphY` re-arms its redraw from an effect every 100 ms. With a few hundred of them mounted,
  React logs "Maximum update depth exceeded". The GUI avoids both for values that stream.
  Fixes in RAS itself, proposed by the subagent and not tried: in `GraphY.tsx` (PlotData)
  redraw from an interval instead of the effect and `setTrigger` pair; in `PV.tsx` derive `pv`
  with `useMemo` instead of an effect with `SetPv`.
- The pvServer sends severity and time stamp but not the alarm status (STAT). The expert views
  read `<record>.STAT` as a PV of its own.
- The boilerplate has no lock file for its Node packages, so the frontend image is not exactly
  reproducible from one build to the next.
- With login disabled the pvServer does not need MongoDB.

## Found while reading, not yet acted on

- `thermocouples.db` exposes 4 of the board's 16 channels.
- The CO manual says a supply sends an unsolicited `!` when its output is off or its power is
  off. The protocol files do not expect it. The simulator has a switch for it, default off,
  until it is seen on hardware.
- The plan proposes `REK-1:mode:read` and `REK-1:alarm:read`. The CO protocol has no command
  for either.
