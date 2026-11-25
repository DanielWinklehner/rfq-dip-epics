# Status

Last update: 2026-11-24. The gates G0, G1 and G2 are closed. Branch `emulated-iocs` is pushed
to `origin` under its own name (2026-11-24, on your word). No pull request is open.

Everything is built and merged. The system suite and the GUI check pass on the final state.
Nothing is running.

Second round (2026-11-22 and 23): the discharge current loop, the GUI round (the loop's widget,
values set in place, tabs as windows, the logger in the GUI), the data logger with two fix
rounds, and the request records that take over their device's state after an IOC start are
built and merged. Each was verified by me on its branch before its merge. On the merged tree
with all of it (plan 0.15) the system suite (281 passed in 766 s), the GUI check (289 checks)
and the logger's tests (35 passed in 407 s) pass in my own runs. Two changes came after those
runs: a fix of the loop's mode request with its test, and the last round of the logger's
dashboards; what was run for each is in "Running".

After that (2026-11-23, on your word): the first contact of the Matsusada and REK supplies has
no gap any more in which a written voltage is accepted and not sent (P40, task T19). Verified
by me on its branch and merged, plan 0.17.

After that (2026-11-23, on your word): the output permit of the Matsusada and REK supplies acts
as a state. While it is lost and a supply reports its output on, the off sequence is sent again
(P45, task T20). Verified by me on its branch and merged, plan 0.18.

After that (2026-11-23, on your word, answer 29): a switching command written into a supply's
switching record while it is still busy with the previous one is no longer lost; it is sent
when the record is free (P47, task T21). Verified by me on its branch and merged, plan 0.19.

After that (2026-11-24, on your word, answer 30): a finding from those acceptance runs is fixed.
After one late reply the requests and replies of a Matsusada or REK line are in step again
after the first mismatch, and a read of an output state or a setting no longer takes another
supply's reply as its own (P49, task T22). Verified by me on its branch and merged, plan 0.20.
The voltage and current monitors do not get the same check: your decision of 2026-11-24
(answer 31).

After that (2026-11-24, on your word, answer 31): the branch is pushed, and the steps of a first
installation on the real computers are written down in [LAB-SETUP.md](LAB-SETUP.md), with a
script that builds EPICS and the IOC application on a Linux computer
(`EPICS/ioc/host/build-epics.sh`). The script was run in fresh containers of Ubuntu 20.04,
22.04 and 24.04, where both IOCs then started in `real` mode with no device connected. Nothing
of it was run on hardware.

After that (2026-11-24, answers 32 to 34): nothing runs in the lab, the rack computer is wiped
and gets a fresh Ubuntu, the lab computer runs Ubuntu and gets the logger, and you want the
dipole scan off LabVIEW. `LAB-SETUP.md` follows it, the plan is at revision 0.21 (hosts, the
logger's home, a note in work package WP11; no record changed).

After that (2026-11-24, on your word, answer 35): the first stage of the dipole scan is built
and merged, three tasks, each verified by me on its branch and again on the merged tree: the
scan program (T23), the magnet supplies through the NI box (T24), the picoammeter for an
assumed model (T25), and the three together in one device case (T27, two rounds). No IOC
loads the new devices yet, and nothing of it ran on hardware. See "Done".

The lab's files from the rack computer are read (answer 39), and the system is in line with
them (T26, verified by me and merged): the source supply is `AU-20P15-1`, the Faraday cup
`FC1` with two values, five flow meters `FLOW` replace the sensor box. The plan is at
revision 0.22. On the merged head the system suite, six device cases and the plan check pass
in my runs, and I ran a scan by hand in the full emulation. Everything is pushed.

Added after that (2026-11-22), outside the task's scope, when you pointed to Matsusada's driver
CD and your notes: the Linux side of the CO-U32, a udev rule and a read-only probe. Not tested
on hardware. The PDF printout is not built: the task named it as a later addition.

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

**Discharge current loop** (`EPICS/Db/loop.db`, `loops/`, design and operation in `LOOP.md`; subagent, three rounds, merged 2026-11-22)
- What it is: the PID runs in a Python service (`loops/mist2loop`, pyepics) beside the platform
  IOC, as you decided. The loop's records `LOOP-DIS:*` are plain records in `iocHV`. They are
  the operator's interface and a backstop that holds without the service: the filament current
  is written only in PID, never by more than the slew limit per step, never away from the
  output limits, never again after someone else wrote it, and the mode goes to MANUAL with a
  MAJOR alarm when the service's counter stands still.
- It hands back to MANUAL by itself, with the reason as a word: interlock open, REK not on in
  remote, TDK output off, a PV without data or not connected, stale data, the operator wrote
  the TDK set point, the TDK refused a set, the service stopped, any start. A request for PID
  is refused for the same reasons. Nothing returns to PID by itself.
- Settings are records saved by autosave: set point 22 A (your answer 20), its limits, gains,
  output limits, slew, two times. The defaults and where each comes from: `LOOP.md` section 5.
  Everything that is not yours there is an assumption (A30 to A35).
- Run by the lead on the merged code (`594547c`): 28 unit tests of the algorithm and of the
  loop's logic; the build; the system suite (269 passed in 692 s); the closed-loop test on the
  plant model (`make -C emulation test-loop`, 282 s); the plan check. Nothing left running.
- By hand on the emulation with the plant model, by the lead: MANUAL to PID without a bump;
  20 A to 22 A in about 8 s; 18 A to 22 A in about 8 s; a lowered output maximum is followed at
  the slew rate; a lowered set point maximum brings the set point and the loop down; your own
  write to the TDK set point hands back and is not overwritten; killed, stopped and restarted
  service; the rack IOC stopped (MANUAL after 0.3 s) and paused (after about 8 s).
- Numbers on the plant MODEL, not on MIST-2 (last run): step 20 to 22 A with 1.8 s rise time,
  0.7 % overshoot, settled in 4 s; an emission drift of 5 % per minute held within 0.034 A; a
  set point the supply cannot reach ends at the output maximum with a flag and comes back;
  1 write per second to the TDK, its read-back rate unchanged at 10 per second.
- Three things the lead's hand checks found that the subagent's own tests had passed, all
  fixed and now tested: a limit changed in PID left the filament current stuck; a stopped rack
  IOC was not noticed; with an error above about 2.9 A (Ki times the error above the slew
  rate) the loop went to PID and did nothing. The last one would have looked like "the loop
  does not work" on the machine. The unit tests now close the loop on a small plant in Python
  for steps of 2 A and 6 A.
- **The discharge supply's own interlock was wrong and is fixed with it (P35):** with the rack
  IOC stopped, the REK's request was cleared but its output stayed on until the rack IOC
  returned. Now the output is off 0.1 s after a stop and about 8 s after a rack IOC that goes
  silent. `rek.db` and `matsusada_au20p7.db` carry the same change; only the REK takes its
  permit from another IOC, so only the REK is tested for a lost link. Cause, in EPICS base
  7.0.10: a record is not processed when its CP link disconnects, and a calc record keeps its
  last value when an input link fails.
- The platform IOC's Channel Access timeout is 5 s instead of the default 30 s (A34), so that
  a silent rack computer is noticed in seconds.
- Not done: the installation on the platform computer (written in `loops/README.md`, not
  tried); the GUI widget (running, T16); gains measured on the machine (`LOOP.md` section 7
  says how).

**GUI round** (`RAS/mist2/`, `gui/LAYOUT.md`; subagent, task T16, merged 2026-11-22)
- The loop: a widget for the class `loop` built from its roles (mode request beside the mode,
  the reason of the last hand-back or refusal right below, set point and measured value, output
  and error, limit flag, service, the three permits, the three terms, the saved settings). Its
  tag stands between the filament heating supply and the discharge supply on the Overview and
  on the Plasma generator page. Trend: the set point in the graph of the measured value, the
  output in a second graph, redrawn every 0.2 s in the device windows.
- Values set in place (your answer 23): a tag carries the set points and requests of its device
  as fields. Supplies: voltage, current (TDK), output. Valves, ion gauge, turbopump: the
  request. MFC and loop: the set point; the loop also its mode. Enter sends, Escape or leaving
  the field gives the entry up, an entry not sent is marked, mouse wheel and arrow keys change
  nothing. The vent valve asks first, nothing else does. Saved settings (current limits, the
  loop's gains and limits) stay in the device window. The drawings were rearranged for the
  taller tags, and the "Reserved: control loop" box is gone.
- Tabs as windows (your answer 24): a control on each tab opens the page as a browser window
  of its own (`/page/<name>`). The tab stays and is marked. "Attach to the main window" or
  closing the window brings the page back. All windows close with the main window.
- Verified by me on the branch: `gui-check.sh` exit 0 with 270 checks (new: the loop, values
  set in place, tabs as windows), and a session in a headless browser with the plant model at
  20 A: set point 21 A typed into the loop's tag and PID from the tag (21 A after about 8 s,
  no window opened by the clicks); a filament current typed into the supply's tag while in PID
  (hand-back "written by someone else"); the Plasma generator page out, PID from there, the
  same values in both windows, attached again; an entry given up by leaving the field; wheel
  and arrow keys. On the merged whole with the logger: `gui-check.sh` exit 0, 273 checks.
- Fixed by me after the merge: the loop's reason, limit flag, output, error and terms were
  INVALID after an IOC start until they were written (records never processed). They are now
  processed once at the start, and the IOC restart test checks it.
- The logger in the GUI (T16b, merged 2026-11-23): the control system services have no page.
  The logger is on the Infrastructure page with a widget of its own, in its device window, and
  as a chip in the status strip of every window ("Data logger: alive", red with "not alive"
  while its counter stands). Without the logger running the chip is red: that is the truth.
  The loop's permits carry their names from the plan, and the list of trends comes from the
  plan. Verified by me: the acceptance command exit 0 at the first attempt (289 checks). The
  engineer's own run passed at the fourth attempt: two runs failed on connections that did not
  come in time while three engineers loaded the machine, one on a text comparison (corrected).
- Fixed by me, at the second attempt: the loop's mode request is defined from the IOC's start
  on, so its buttons are not drawn INVALID after a start. My first fix only had the record
  processed at the start, which leaves a binary output without a first value undefined, and
  its test passed only when the loop service had already written the request. The GUI check's
  note after an IOC start showed it. Now the record starts defined, and the test holds the
  service paused across the IOC's restart: seen failing without the fix and passing with it.
- Known: with values set in place a filament current typed on the Overview takes the source
  out of PID at once (question 12).

**Data logger** (`logger/`, `EPICS/Db/logger_status.db`, design and operation in `LOGGER.md`; subagent, task T17, merged 2026-11-22, fix round running)
- What it is: a Channel Access logger of our own (`logger/mist2log`, Python with pyepics) in
  front of TimescaleDB, with Grafana, as a Compose project of its own (`make -C logger up`,
  `down`, `test`, `read`). It subscribes with monitors, never polls, and logs 180 PVs: 44 raw
  (30 days), means, minima and maxima per second (2 years) and per minute (for ever), and an
  event log kept for ever (set commands, alarm changes, states, the interlock, the loop's
  mode, the logger's own events). Which PV goes where is in the plan (section `logging`, rules
  with reasons); a PV without a tier is a warning of `build.py`.
- A constant value costs nothing and a gap is a row of its own, so a reader never holds a
  value across a disconnect. The reading tool and the database functions hide both.
- While the database is away the logger buffers (2 000 000 rows, about 4 hours of the
  emulation) and writes when it returns. Its state is in the rack IOC (`LOGGER:*`): a dead
  logger or a lost database is a MAJOR alarm.
- Measured on the emulation: 103 raw rows and 36 second rows per second, 1.5 % of one core,
  about 370 GB of disk after two years (the per-second tier is 322 GB of it), then about 5 GB
  per year. The arithmetic is in `LOGGER.md` section 10.
- Verified by me on the branch: plan check, system suite (271 passed in 697 s) and the
  logger's tests (28 passed in 332 s), each exit 0, saved settings unchanged, nothing left
  running. And a session with the plant model in PID at 22 A: my own Channel Access monitor
  of `REK-1:current:read` for 90 s, the database stopped for 32 s of it, the door opened.
  533 updates, 533 raw rows, none missing, extra or different. The per-second tier equals my
  own time-weighted means in 87 of 87 seconds. The event log has the trip in the right order.
- Found in that session and fixed in the round T17b (merged 2026-11-23): the loop's writes of
  the filament current filled the event log (63 set commands in 78 s of PID, kept for ever);
  the mode event of a hand-back carried the reason from before it; Grafana never showed finer
  than one value per minute; the dashboards lacked the loop's graphs; a batch the database
  rejects was tried again for ever. Now the plan says which PV a loop writes (`drives` of
  `loop.db`), and the logger stores it as a signal while the loop is in PID and as set
  commands otherwise.
- Verified by me after T17b: the three acceptance commands (271 passed in 703 s, 33 passed in
  343 s), and my session repeated: 117 s of PID without one set command of the filament
  current, my own capture of that PV (57 updates) equal to the raw rows and to the seconds
  tier (97 of 97), the hand-back's mode event with "interlock open", a dashboard over 5
  minutes with raw data. The rejected batch I checked in the code and by its test only.
- Round T17c (merged 2026-11-23): a value that does not change within the window was returned
  as one point. The trend function and the reader now repeat it before every gap and at the
  end of the data. Verified by me: `make -C logger test` (35 passed in 406 s) and the rows the
  function returns for the loop's set point.
- Round T17d (merged 2026-11-23): Grafana still drew no line for such a value. In a panel with
  several series the lines were broken at every point of the other series, so dense series
  showed as rows of dots and a constant one disappeared. The panels now split the rows into
  one series each. Verified by me: `make -C logger test` (35 passed in 408 s) and a dashboard
  over 5 minutes after a minute of PID and a trip: every trace a continuous line, the loop's
  set point a line at 22 A.
- Not done: where it runs (the plan's question), a backup timer, synchronised clocks (P33).

**Request records after an IOC start** (`EPICS/Db/first_contact.db`; subagent, task T18, two rounds, merged 2026-11-23; open point P25)
- The requests of the valves (`VALVE:s1` to `s8:set`), the turbopumps (`TURBO1/2:start:set`)
  and the ion gauge (`AIM:enable`) were undefined (INVALID) after every start of the rack IOC
  until an operator wrote them, and showed "closed" or "stop" for an open valve and a running
  pump. Now each takes over the state of its device at the device's first answer, and nothing
  is sent for it: the request is processed once in simulation mode. Without an answer it
  stays INVALID. A write of a client before the take-over wins.
- The ion gauge got an internal record that reads "cold cathode on" from the status word of
  the pressure replies (`AIM:_enable:get`), without a request of its own.
- The first version did the three steps (simulation on, copy, simulation off) with a `seq`
  record and argued that they are one run. I read the source of our EPICS base: a `seq` hands
  every step to a callback and releases the lock in between. A write in those gaps would have
  been accepted and not sent, or sent and then undone. Sent back. The second version is one
  check and three chained records that run under one hold of the lock; I checked the source
  lines it relies on.
- Verified by me: plan check, system suite (281 passed in 743 s, saved settings unchanged) and
  GUI check, each exit 0; and by hand: pump 1, foreline valve, MFC shutoff valve, a spare
  relay and the gauge on, then the rack IOC restarted. Every request showed its device's state
  without alarm, simulation mode was off, the simulators had received no set, the Overview
  had no INVALID request, and a write afterwards was sent.
- The same `seq` pattern was in the first contact of the Matsusada and REK supplies from the
  first round (P40): removed by T19, next block.

**The supplies' first contact without a gap** (`EPICS/Db/supply_first_contact.db`; subagent, task T19, one round, merged 2026-11-23 on your word; open point P40)
- What was wrong: the voltage set point of a supply starts in simulation mode, takes the
  supply's own setting at the first valid echo, and then leaves simulation mode. The two steps
  were two callbacks of a `seq` record with the lock released in between. A voltage written
  between them was accepted without alarm, not sent and not replaced: the set point then
  showed a voltage the supply did not have. The take-over of the output state had the same
  structure.
- What it is now: a database file of its own, loaded with every supply (four AU supplies on
  the rack IOC, the REK on the platform IOC, macro `S`). The take-over of the output state
  (`_init:otake`) and of the voltage setting (`_init:vtake`) are each one check and two or
  three chained records that run under one hold of the lock. A write comes before the check
  (in simulation mode, then replaced by the supply's setting) or after the last step (sent).
  `_init:vcopy` is removed. `output:init` keeps what follows the take-over: the echo read,
  the current limit, and the gate 5 s later.
- What an operator sees is unchanged: nothing is sent before the first answer, a voltage or a
  request written before it is replaced by the supply's state (P20, P29), the current limit
  is sent after the first contact, and a supply that answers late is taken over then.
- I read the source lines the design rests on in the base of our image: StreamDevice finishes
  a record between `dbScanLock` and `dbScanUnlock` (`StreamEpics.cc`, `recordProcessCallback`),
  an input record runs its forward link inside its own processing, `calcout` with a delay of
  0 writes at once, `dfanout` writes all its outputs and then its forward link without a
  callback, and a client's write takes the same lock (`dbAccess.c`, `dbPutField`).
- Tests: the structure from the running IOCs (types, no delay field, the chain of links, no
  step of a take-over left in the supplies' own files), and a client that writes an AU
  supply's and the REK's voltage set point in a tight loop while their IOC restarts, the
  supply silent at the start so that writes really go into simulation mode. Whenever
  simulation mode is off, the set point equals the simulator's setting. They ride on the two
  IOC restarts the suite had, so the suite got 3 s longer, not 30.
- How the new test was seen to fail: with the gap widened to 0.3 s (the engineer's run) it
  reports set point 40 V against 0 V at the supply. With the old records as they were it did
  not fail in 11 637 writes over 11 restarts: the real gap was too short to hit on purpose.
  The structure test fails on the old records.
- Verified by me on the branch: plan check, system suite (284 passed in 757 s, saved settings
  unchanged, 1101 writes through the REK's restart and 1454 through the AU supply's), the
  Matsusada device case (28 passed in 238 s) and the GUI check (exit 0, 289 checks). By hand:
  AU-20P7-1 on at 12 kV and AU-20P7-3 off at 3 kV, the rack IOC restarted; the REK on at
  100 V, the platform IOC restarted. Each time set point, echo, request, `ToggleOutput` and
  the supply's state were as before, simulation mode off, the gate enabled after its 5 s
  without switching, and the simulators had received one command per supply: the current
  limit. With AU-20P7-1 silent at the start I wrote 5 kV and "off" before it answered: both
  were replaced by 12 kV and "on" when it answered, and nothing was sent. Writes afterwards
  were sent (11 kV, 80 V, on, off).
- On the merged head (plan 0.17): plan check, and the system suite once more (284 passed in
  757 s, saved settings unchanged, nothing left running).
- `output:init` lost its guard (it was disabled while the probe had no valid answer), because
  only the take-over starts it now. A client that writes this internal record before the
  first contact would enable the gate early. With the request and the gate's previous value
  both at 0 nothing is sent then. Read from the records, not tested.
- Seen in the hand check, and as designed: a restart of the rack IOC switches the REK off and
  clears its request, because the REK's permit is a PV of the rack IOC.
- Found beside it, both older than this task: P45 (a rare case in the interlock gate's
  switching sequence) and P46 (how long the loop service needs after an IOC start).

**The output permit as a state** (`_permit:enforce` in `EPICS/Db/matsusada_au20p7.db` and `rek.db`; subagent, task T20, two rounds, merged 2026-11-23 on your word, answer 27; open point P45)

- What was wrong: the gate `OutputIntlk` sends its off sequence once, when its result changes.
  That one write can be lost (P45): `ToggleOutput` still busy with a switch-on, and the gate
  processed by its own 1-second scan, which EPICS does not let mark a busy record to run
  again. The supply then stays on with the permit lost and the request cleared. The same
  state arises when a client writes `ToggleOutput` directly while the permit is lost (P28),
  or when someone switches on at the front panel.
- What it is now: one internal record per supply, `_permit:enforce`, evaluated every second.
  While the gate is enabled, the permit is lost (the gate's and the latch's own condition) and
  the supply reports its output on by a valid reading (the SW setting `read_output_status`,
  or the status `status:read` ON or "ON, LOCAL"), it starts the gate's off sequence again:
  REN, RST, SW0 and the read-back. It acts when this held at two evaluations in a row and
  then counts again, so the first sequence goes out 1 to 2 s after the IOC has the reading
  and one more every 2 s while it lasts. It does not count while a switching is under way
  (`_out:switch` or `ToggleOutput` active). Its value is the number of sequences it has
  started since the IOC start, 0 in a system where nothing went wrong.
- It only switches off. It never switches on and never writes the request (the latch does).
  REN comes first, so a supply under local control is taken back, as the gate does at a
  permit loss.
- What changes for an operator: while the permit is lost, a direct write of `ToggleOutput`
  lasts 1 to 2 s and a switch-on at the front panel 2 to 3 s (the status is polled once a
  second). With the permit present both act as before. Before the gate is enabled (first
  contact plus 5 s) nothing is sent. A normal permit loss still sends one off sequence.
- A supply that does not answer is not flooded: a reading that is INVALID does not count, so
  the sending stops, and starts again when the supply answers and still reports on.
- The check and the start of the sequence run under one hold of the lock set. I read the
  lines the argument rests on in the base of our image: the periodic scan processes a record
  between `dbScanLock` and `dbScanUnlock`; a `seq` fixes its link groups when it starts and
  stays active until its last group has been written (`seqRecord.c`), so a later write of its
  selection does not change a running sequence; a write through a database link marks a busy
  target to run again only when the writer carries the put flag (`dbDbLink.c`,
  `processTarget`), which a change event and a client's write give (`db_access.c`,
  `db_process`; `dbAccess.c`, `dbPutField`) and the periodic scan does not.
- **The first version had a fault that came from my brief.** I had asked that the rule wait
  while a read of the SW setting is under way. The engineer found that this stretched the
  reaction to 1 to 4 s, because that read runs every 5 s on the same time grid as the rule.
  Reading the scan code I found it worse: a periodic scan list is ordered by record type, so
  with the read period `SCAN_GET` set to 1 second the read stands before the rule at every
  evaluation and the rule never acts. The engineer showed it (supply on for the 20 s watched,
  count 0) and showed it gone (off after 1.78 s) with that input removed. A structure test
  now refuses any such input whose record is scanned periodically.
- Tests, device case `emulation/devtest/matsusada` (19 new, for one AU unit and one REK unit
  unless said): the state the fault leaves (also for a unit that is not polled); the front
  panel; nothing with the permit present; 120 normal permit losses with one SW0 each and the
  count unchanged; a supply that reports on and falls silent; an IOC start with the output
  on and the permit lost; the structure read from the running IOC. In the system suite one
  addition: while the door is open `ToggleOutput` of all five gated supplies is written to 1
  and all are off again within 4 s, counted once each.
- How the tests were seen to fail (the engineer's runs): with the rule switched off the tests
  of the state, the front panel, the silent supply, the structure and the suite's addition
  fail; with a rule that acts at once and ignores the gate's state the 120 losses fail in the
  first round and the IOC start fails; with a rule without the permit condition the test
  "nothing with the permit present" fails.
- One test was changed by me: the IOC-start test wrote the permit after its Channel Access
  client had found the restarted IOC, which in my first run took longer than the 5 s after
  which the gate is enabled, so it failed. The supplies now stay silent until the permit is
  written. It passed twice alone and in the whole case, and failed against a rule that reads
  the permit itself and ignores the gate's state.
- Verified by me on the branch: plan check; system suite (284 passed in 777 s, saved settings
  unchanged); the Matsusada device case (47 passed in 437 s, after the change above; before
  it 46 passed and that one test failed); the GUI check (PASS). By hand with the door open:
  `ToggleOutput` written to 1 switched AU-20P7-1 on and it was off again after 1.54 s, the
  REK after 1.59 s, each counted once, the simulators had received RST, SW1 and then RST, SW0.
  AU-20P7-3 taken under local control and switched on at the front panel received REN, RST,
  SW0 after 2.27 s. With the permit present the same direct write stayed on for the 6 s I
  watched and was not counted. A normal permit loss with AU-20P7-1 and the REK on sent one
  RST, SW0 to each and the counts did not move.
- On the merged head (plan 0.18): plan check, and the system suite once more (MERGED).
- Asked of the engineer as a report, confirmed by me in the source, not changed: P47.
- Seen once in the engineer's runs, not in mine: the older device test
  `test_limit_survives_an_ioc_restart` did not find all PVs of AU-20P7-1 valid within 20 s of
  a restart. It passed in every other full run of the case (three of the engineer's, two of mine). Its
  failure message names the PVs now. P48.

**A switching command is not lost** (`_out:resend` in `EPICS/Db/matsusada_au20p7.db` and `rek.db`; subagent, task T21, one round, merged 2026-11-23 on your word, answer 29; open point P47)

- What was wrong: `ToggleOutput` sends RST and SW0 or SW1 and reads the SW setting back, which
  takes some tens of milliseconds. A value written into it meanwhile is stored and not sent,
  unless EPICS marks the record to run again, which it does only for a writer with the put
  flag: a client's write and a change event have it, a periodic scan has not. The gate is
  also evaluated by its own 1-second scan. So an off that followed an on within the switching
  time could be stored and not sent (P47), and the supply stayed on with its request off.
- What it is now: one internal record per supply, `_out:resend`, evaluated every second. When
  `ToggleOutput` is not busy and its value differs from the value it last started to send
  (`VAL` against `RVAL`), it processes `ToggleOutput` once. It sends what is in the record, on
  or off, which is the gate's latest command, and changes no value. Its value counts the times
  since the IOC start, 0 in a system where nothing went wrong.
- Not the remedy I had named to you (the gate evaluated through Channel Access). That one
  rests on EPICS's "run again" mark, which a second change within the start of a sequence
  takes away again, and it adds a dependency. This rule looks at the state of the record and
  holds for any number of writes.
- What it rests on, read by me in the base and StreamDevice of our image before the brief and
  again in the engineer's citations: a `bo` record sets `RVAL` from `VAL` when it starts to
  process and not while it is busy (`boRecord.c`, `process`); the command line is formatted
  from `VAL` when it is reached (`devboStream.c`, `StreamCore.cc` `evalOut`); the reply is
  only compared; a record processed while busy is left alone (`dbAccess.c`, `dbProcess`).
- It ends: after its processing `VAL` equals `RVAL` unless a new value was written, also when
  the supply does not answer. A silent supply gets the stored command once.
- Nothing goes out twice on the event path, where EPICS runs the record again by itself: the
  rule then finds the record busy or `VAL` equal to `RVAL`.
- Nothing else writes `ToggleOutput` without processing it; I went through every writer in
  the databases ("All HV off" goes through the requests, the first contact processes it in
  simulation mode under one hold of the lock).
- Tests, device case only (25 new; the suite's time is used up, P32). The lost write is made
  on purpose by a helper that exists only in the device case: records processed by a
  periodic scan write into `ToggleOutput` through a database link while the simulator
  answers 100 ms late. For one AU unit and one REK unit, both directions, without and with
  the rule; several values while busy (the last is sent); a row that ends on the value being
  sent (nothing more is sent); an off by the request during a switch-on (each command once);
  a silent supply; an IOC restart (both counts stay 0); the structure. The 120 normal permit
  losses of T20 also check that this count does not move.
- Seen by me, in my run of the device case: an off written 100 ms into a switch-on of
  AU-20P7-3. Without the rule `ToggleOutput` showed 0 with an INVALID alarm, `RVAL` 1, and
  the simulator's output stayed on for the 4 s or so until the test enabled the rule. With the rule
  RST and SW0 went out 0.64 s after the record was free and the alarm cleared. With the
  rule's scan set to Passive in the database (my own change, restored afterwards) 20 of the
  25 new tests failed; the 5 that passed are those that check that nothing extra is sent.
- Verified by me on the branch: plan check; system suite (284 passed in 767 s, saved settings
  unchanged); GUI check (PASS); the Matsusada device case 72 passed in 602 s in its second
  run. In its first run 70 passed and two tests of T20 failed, before any test of T21 had
  run: the cause was P49, not the rule (the simulator had received no switching command
  beyond the expected ones).
- On the merged head (plan 0.19): plan check, and the system suite once more (MERGED).
- Known and harmless, P50: two cases in which a command goes out without or twice.
- Found in my first device-case run, older than both tasks: P49.

**A late reply on a Matsusada line** (`EPICS/Db/matsusada_co_ctrl.proto` and `rek.proto`; subagent, task T22, one round, merged 2026-11-24 on your word, answer 30; open point P49)

- What was wrong: of the supply's replies only the one to the status request (STS) carries
  the unit number. A reply that came later than the reply timeout (150 ms) and the wait after
  it (50 ms) was read by the next request on the line, and from then on every request was
  paired with the reply to the one before it. A line with two polled supplies is kept full by
  the monitor reads, so nothing discarded the stray reply and the state lasted until something
  else broke it. The requests of two supplies alternate on a full line, so one supply read
  the other's reply of the same kind and showed it without alarm.
- Seen by me with the old files, in the full emulation: the source supply at 4 kV, the puller
  at 12 kV, one reply of the source made 300 ms late, three times 4 s apart. The line did not
  come back in step in the 12 s I watched. After the first late reply the puller showed
  4000 V and the source's current, without alarm; after the second the monitors of both were
  INVALID; after the third the source showed 12 kV. In the device case: 167 values of the
  neighbour in 9 s after one late reply.
- Worse, read from the databases for the brief and then seen in the device case with the old
  files: at an IOC start with one supply's replies late, the first contact copied the
  neighbour's output state. The supply that was off stood with its request on, the one that
  was on with its request off. A state read, a setting read and the read-back of a switching
  or a set took the neighbour's reply the same way: `ToggleOutput` confirmed a switch-on that
  the supply had not executed.
- What it is now, two parts, both in the protocol files only (no record changed):
  1. After a mismatch the line is kept for 50 ms (`@mismatch { wait 50; }`). The reply that is
     still on its way arrives in that time (37 ms at most: request, turnaround, reply) and
     StreamDevice discards it before the next write. One mismatch, then in step. This also
     covers a line nobody asked for (the "!" a unit sends when its output goes off).
  2. Every protocol that reads an output state or a setting (SW?, CH0?, CH1?, as a read and
     as the read-back of a switching or a set, and the first-contact probe) first sends STS
     to the same unit and checks the unit number in the reply. A stray reply is older than
     every reply to a later request, so it is the first thing such a protocol reads, and it
     fails the check: the record turns INVALID instead of taking another supply's value.
     A command goes out before the check, as before, so a stray never stops a command.
  The second part is my addition to what I had named to you (answer 30).
- The monitors (MN1, MN2) are not checked, because the check would halve their rate. What
  that leaves is P51.
- What it rests on, read by me in the StreamDevice of our image before the brief and again in
  the engineer's citations: input that arrived before a write is discarded
  (`AsynDriverInterface.cc`, `writeHandler`); a handler's commands run before the line is
  released and the record keeps the original error (`StreamCore.cc`, `finishProtocol`); the
  skip flag works with an enum (`StreamCore.cc`, `matchInput`).
- Measured, in my run of the device case with the new files:
  - one late reply on a line of two polled supplies, at 12 random moments: one TIMEOUT, one
    mismatch (CALC), then in step, every time. In 10 of 12 the neighbour's monitor accepted
    one value of the same kind and showed it for 0.15 to 0.20 s; in 2 none;
  - three polled supplies: one value in 10 of 12, shown 0.20 to 0.54 s;
  - a late reply of each kind (MN1, MN2, STS, the status check, SW?, CH0?, CH1?): in step
    after one mismatch;
  - a state or setting read after a neighbour's late reply, six protocols: INVALID once, its
    own value kept, never the neighbour's;
  - an IOC start with one supply on, the other off, different settings, the first one's
    replies late for 12 s, both directions: each supply took over its own state and its own
    setting, and no switching or set command went out;
  - a "!" on the line: one mismatch at once, in step 50 ms later.
- The same in the full emulation, by hand (rack IOC, source 4 kV, puller 12 kV, three late
  replies): each time one TIMEOUT, one value of the source shown by the puller, one mismatch;
  in step 0.41 to 0.56 s after the fault.
- The cost: the status check adds 0.6 requests per second per supply (about 1.3 % of the
  line). On a full line the monitors update at 8.95 Hz instead of 9.2 with two supplies at
  5 ms turnaround, 5.9 instead of 6.1 at 16 ms. A supply that does not answer costs what it
  did (200 ms per request): its neighbour keeps 1.35 to 1.40 updates per second.
- Tests, device case only (21 new in `test_stray_reply.py`, two simulated lines of their own
  so that the late replies do not disturb the other tests). The simulator has one new fault
  mode, `slow_second` (the second reply after it is set comes late, once), because with the
  status check the reply to the query itself is the second of its protocol.
- Verified by me on the branch: plan check; system suite (284 passed in 758 s, saved settings
  unchanged); GUI check (PASS); the Matsusada device case 93 passed in 1062 s. With the old
  protocol files put back by me, the ten tests of the fault, the state reads, the first
  contact and the "!" all failed, each with the neighbour's value named.
- On the merged head (plan 0.20, a comment in the protocol files corrected by me): plan
  check, and the system suite twice. The first run failed one test (283 passed, 1 failed),
  `test_fault_turns_its_pvs_invalid_and_recovers[rek-close]`: 3.5 s into the REK's fault both
  lines of the rack simulator gave no reply within 150 ms, 5 ms apart, so the current monitor
  of one supply on each line was INVALID for one cycle, and that test allows no INVALID on
  another device while a fault lasts. No mismatch followed. It is a pause of the simulator,
  the kind of event that showed P49, on lines that had nothing to do with the fault under
  test; its cause is not known (P54). The second run: MERGED.
- One test file of the rates was changed by the engineer: `test_rates.py` derives the status
  polls from the simulator's reply count and now subtracts the status checks. Nothing else
  in it changed.

**The dipole scan, first stage** (three subagents in parallel, tasks T23, T24, T25, one round
each, merged 2026-11-24 on your word, answer 35; work package WP11)

- What it is: the devices of the dipole scan as PVs and the scan as a Python program that
  talks to PVs only, in place of LabVIEW. Three parts, each proven in a device case of its own.
  No IOC of the emulation loads the new databases, so the system suite, the GUI and the logger
  are untouched. Nothing ran on hardware.
- **The scan program** (`scans/mist2scan`, `docs/emulation/SCAN.md`, T23): steps one set point
  through a list of values, in part steps where a move is large; waits until the read-back is
  valid and within the tolerance; then collects each detector for the dwell time and writes
  one row per point (time-weighted mean, spread, number of values, minimum, maximum, validity).
  A value taken while its PV is INVALID or not connected is not used, and a point without a
  valid value is recorded as missing with the reason. It writes one PV, the actuator, never
  outside the definition's limits or the PV's control limits, and refuses to start otherwise.
  Every end (completed, a condition lost, a detector lost, ctrl-c, SIGTERM, an error) takes the
  actuator back in part steps and leaves the data on disk with the reason; after a lost
  actuator nothing more is written. `scans/config/dipole.yaml` is the dipole scan with the
  plan's PV names; every number in it is ASSUMED.
- **The magnet supplies** (`daq/mist2daq`, `EPICS/Db/dipole.db`, `docs/emulation/DAQ.md`, T24):
  a Python service owns the NI USB-6001 and serves its channels as a libcom1 device over TCP,
  so the IOC uses the unmodified `libcom1.proto`. Records `dipole:current:set` (acknowledged),
  `dipole:current:get`, `dipole:current:held` (what the service holds). The service writes no
  output by itself: at its start the held value is "not known" (shown INVALID, not 0), a set
  outside its limits is refused, and when the IOC goes silent it holds (a ramp to zero is a
  setting, off). After an IOC restart the set record takes over the held value and nothing is
  sent. The backend for the real box is written from NI's documentation and NOT VERIFIED.
- **The picoammeter** (`EPICS/Db/picoammeter.db`, `keithley6485.proto`, simulator,
  `docs/emulation/PICOAMMETER.md`, T25): built for a Keithley 6485 (assumption A44) from its
  manual, every command with its page. `pico1:current:get` is INVALID, with the number kept,
  while the reading is no measurement (zero check on, which is the state after power-on;
  overflow; overvoltage). Range and zero check are requests that take over the instrument's
  state at the first contact; an IOC start sets nothing. Every poll starts with `ABOR` and
  ends with `INIT`: while it measures continuously the instrument executes no query (manual
  7-4, read by me in the manual's text), and neither command changes a setting.
- **Verified by me** on each branch and again on the merged head `b94a089`, all exit 0: the
  scan program's unit tests (57) and device case (10 passed in 105 s; the three peaks of the
  case's database found at -6.003, 0.500, 5.499); the DAQ service's unit tests (47), its
  replies against the real libcom1 library (122 lines, 0 differences) and its device case (12
  passed in 48 s); the simulators' tests (143) and the picoammeter's device case (11 passed in
  122 s); the plan check. One variant of my own per task, each seen to fail and put back: an
  INVALID value taken as valid (the scan's test of the INVALID detector fails), `PINI` on the
  magnet's set record (the tests of "nothing written at the start" fail), zero check left out
  of the bits that make a reading no measurement (the power-on test fails).
- **Since then:** the three together (next block); the scan in the full emulation by my own
  hand, on the merged head with the names of T26 (source supply voltage against the Faraday
  cup current: `check` exit 0, 15 points in 70 s, exit 0, the cup current 1.07 mA at 1 kV and
  3.07 mA at 15 kV as the plant model has it, the supply taken back to 1 kV, the saved
  settings unchanged); the plan's entries (revision 0.22).
- **Not done:** an IOC that serves the dipole (which computer: your word).

**The dipole scan, the three parts together** (subagent, task T27, two rounds, merged
2026-11-24)

- A device case `emulation/devtest/dipolescan`: the shipped scan program runs the shipped
  definition `scans/config/dipole.yaml` through one IOC against the DAQ service and the
  picoammeter simulator. A small model of the case couples them: three peaks over the magnet
  current, at 10, 14.14 and 17.32 A (the ratio of the square roots of 1, 2, 3). No number of
  it is measured on MIST-2.
- What it shows, in my run of the second round (11 passed in 463 s): after power-on the scan
  refuses and writes nothing (zero check is on, and the service holds no value); the three
  peaks are found within 0.001 A; with a fixed range below the highest peak the scan ends at
  the overflow, as shipped; a stopped service, a silent picoammeter and an IOC restart in the
  middle each end the scan cleanly.
- **Found and corrected in the scan program** (each with a test that failed before):
  - With the DAQ service stopped, the end move wrote every part step into a set PV the IOC
    could not send, and the file named the end target as the last write. The end move now
    stops at the first write the IOC does not confirm.
  - A stopped service ended a scan only after the settle timeout (30 s), and after a service
    restart the set PV still showed a value the service no longer held, so a scan would have
    started from it. New key `actuator.held` (the PV of what the device holds): the scan
    refuses to start when it is INVALID or differs from the set PV, and ends at once, writing
    nothing more, when it goes INVALID. Measured: 0.10 s after the stop.
  - New key `actuator.readback_lost_after` (default 5 s): a read-back that stays INVALID that
    long is "actuator lost", also for an actuator without a `held` PV.
  - Every INVALID reason names the alarm status: an overflow is "INVALID (STATE)", a silent
    instrument "INVALID (TIMEOUT)".
- **The numbers together:** the picoammeter delivers one value per second. With the shipped
  dwell, now 3 s (ASSUMED), a point gets four readings and takes 6.5 s; 26 points took 178 s.
  The settle time must not go below 1.3 s (the picoammeter's poll period plus one reading).
- **Verified by me**, each round on its own: all acceptance commands (the new case, the three
  part cases, the simulators' tests, both sets of unit tests, the plan check), two of the
  case's tests alone, and two variants seen to fail and put back: the scan program without
  the end-move correction (it writes 9, 8, 7, 6 A after the stop), and the shipped definition
  without `held` (the three tests of the stopped service fail). In the first round I found
  that the case's tests depended on their order; the second round removed that.

**The system in line with the lab's files of 2026-11-24** (subagent, task T26, one round,
merged 2026-11-24; answer 39, `reference/lab-2026`)

- **The source supply is `AU-20P15-1`** everywhere (rack IOC, first contact, all-off,
  `limits.defaults`, plan, registry, documents), with no alias: the old name was this
  system's assumption. A limit saved under the old name is dropped once at the next IOC
  start (the default applies); in the emulation that was the same value.
- **The Faraday cup is `FC1`** with the lab's record names (`FC1:data`, `FC1:i1:getcurrent`,
  `FC1:i2:getcurrent`), on a USB serial line (115200 8N1). No unit, because none is known.
  **The flow meters are `FLOW:f1:getflow` to `f5`** in l/min, from the lab's database and
  the sketch's arithmetic (1260 pulses per litre, counted for 0.5 s). Both run on a
  simulated board of libcom1 protocol 1 (a new option of the simulator, checked against the
  real library of that version), since that is what the lab's boards are: only the query
  `A`, no identity records.
- **The sensor box is out of the rack IOC**, the GUI and the logger; its database and device
  case stay. In the plan it is marked as replaced.
- **The MFC was compared and left unchanged.** Ours serves both PVs of the lab's file. The
  lab's protocol file ends every message with a carriage return, ours with `;FF` alone as the
  MKS supplement says. In a test against a fake unit ours read every reply form with and
  without the carriage return; the lab's file alarmed without it.
- **Names of the serial devices:** `EPICS/ioc/host/99-mist2-serial.rules` gives the gauge
  controller, the interlock box, the valve box and the MFC their names by serial number.
  The Matsusada adapters, the Prolific adapters and the Optas are named by their USB socket
  (`LAB-SETUP.md`). Both rule files pass a syntax check; not tested on hardware.
- **Verified by me** on the branch: the system suite (282 passed in 768 s, saved settings
  unchanged), the GUI check (PASS, 289 checks), the logger's tests (35 passed in 407 s), the
  device cases `faradaycup` (9), `flowmeters` (9) and `libcom1_devices` (82), the simulators'
  tests, the plan check. My own variant: without the alarm links in the two new databases,
  the tests of a silent board fail in both cases. On the merged head `ad22e54`, with plan
  0.22: the suite again (282 passed in 767 s), six device cases, the plan check.
- One line of the logger's tests was changed by me, with the engineer's diff: the logger's
  database keeps the PVs of earlier registries, and a test took the first of them by name.

**The interlock box as an Opta** (subagent, task T28, one round, merged 2026-11-25; answers 53
and 54)

- **The firmware** `AVR/devices/InterlockOpta` answers with the old box's four channels in the
  same order on USB serial, so `interlockbox.db`, the port and every PV stay; only `INTLK:id`
  reads `InterlockOpta`. The doors are on inputs I1 and I2 (high = closed, A48). Relays 1 and 2
  are on only while both doors are reported closed, decided in the Opta without the IOC; relays
  3 and 4 are the old box's two relays switched by command. A door that opens is reported open
  for at least 1 s. No latch. A hardware watchdog of 8 s. **It is compiled for the Opta and
  tested on a PC. It has never run on a board** (P61, P62).
- **A compile in a container** with fixed versions (`AVR/tools/compile.sh`, image
  `mist2-arduino:dev`: arduino-cli 1.5.1, Arduino's core 4.6.0 for the Opta and 1.8.8 for the
  Mega): the Opta sketch (143072 bytes, no warning) and the two Mega sketches, the valve box's
  as flashed on 2026-11-24 among them.
- **Tests on a PC** (`make -C AVR/devices/InterlockOpta/tests`): the door decision (hold time,
  a bouncing switch, an opening of a millisecond, the wrap of the millisecond counter after 49
  days), the device through the real library (no line received switches relays 1 and 2, tried
  with every command and 40 000 random lines), and the simulator's entry compared with the
  firmware line by line. The simulated interlock box now reports the Opta's identity and number
  format.
- **Two faults in the firmware library, found by these tests and fixed by me:** a received
  byte of 0x80 or more as the channel letter shifted a negative value (undefined behaviour on
  an Arduino Mega and a PC; a regression test fails without the fix, and a simulated ATmega
  gives the same replies as the PC afterwards). And three symbolic links in the library's
  stand-alone example made the Arduino IDE 2 refuse the whole library on Linux; they are gone,
  the example builds before and after. The valve box as flashed has the old line of the first
  fault: the IOC sends no such byte, so nothing changes for it.
- **The data sheet, read by me** (Arduino's collective data sheet of the Opta, revision of
  2026-11-19): supply 12 to 24 V DC; a digital input takes 0 to 24 V, low up to 4.46 V, high
  from 6.6 V; the relays are normally open with a minimum switching load of 300 mW (12.5 mA at
  24 V, 60 mA at 5 V).
- **Verified by me:** the eight acceptance commands from the engineer's worktree, all exit 0.
  Three variants of my own: with the hold time halved the door test fails, with a command
  allowed to switch relay 2 the device test fails, with the simulator's entry in the old number
  format the comparison fails. The pin names and the calls the sketch uses, read in the
  installed core. On the merged branch, with the library fixes: the system suite (282 passed
  in 767 s, saved settings unchanged), the library's tests (289 checks in each of four
  builds), the sketch's tests, the three compiles, the simulators' tests, the device case
  `libcom1_devices` (82 passed), the plan check. Not rerun: the GUI check (no PV, channel or
  role changed; the registry got the device's new name and notes).

**The foreline gauge (INFICON VGC401) and the Edwards TIC, read only** (subagents, tasks T30 and
T29, one round each, merged and loaded into the rack IOC on 2026-11-25; answers 58, 59):

- **VGC401** (`vgc401.db`, `vgc401.proto`, 9600 8N1): `PRESSURE:foreline:getpressure` in torr,
  converted from whatever unit the controller is set to, with `:getstate` (the manual's status
  words; below and above range the value stays with MINOR, every fault is INVALID with NaN),
  `:getgauge` (the head the controller identified), `:getunit`, `:geterror`, `:getversion`.
  Requests for readings only. The controller sends by itself after power-on; the IOC's first
  request ends that until it is switched off and on (manual p. 55).
- **TIC** (`tic.db`, `tic.proto`, 9600 8N1 Xon/Xoff): the three gauge sockets
  (`TIC:gauge<n>:getpressure` in torr, state, units, alert, priority), the turbopump (state,
  type, speed), the backing pump (state, type), the variant and the identity. Queries only: no
  command, no setup message. A socket without a gauge and a pump the controller does not have
  are INVALID with the reason in the state.
- **A probe for each** (`EPICS/ioc/host/inficon_vgc401_probe.py`, `edwards_tic_probe.py`), which
  runs without an IOC and prints every raw reply with its time. Pushed ahead of the rest so
  that the owner could run them.
- **Simulators** `inficon_vgc401` and `edwards_tic`, a device case for each
  (`emulation/devtest/vgc401`, 23 tests; `emulation/devtest/tic`, 13 tests), documents
  `VGC401.md` and `TIC.md`.
- **Loaded by me:** `st.cmd`, both port files (device names `/dev/mist2/vgc401` and
  `/dev/mist2/tic` are placeholders without a rule), the simulator's configuration (ports 5034
  and 5035), the plan (revision 0.29: device `gauge_foreline` filled in, device `tic` new, the
  rules of both databases, a logging tier for calc records), the registry.
- **Verified by me:** each engineer's acceptance commands from his worktree; four pages of the
  VGC401's manual against the engineer's quotes (automatic sending, the request and its
  acknowledgement, the status digits, the units); that neither probe, protocol file nor
  database holds a command or a setting; then on the merged branch, with both devices loaded:
  the plan check (38 tests, no warning), the simulators' tests (175), both device cases (23 and
  13 passed) and the system tests (**296 passed**, 2 deselected, in 807 s; 282 before, 14 more
  for the two devices). Not rerun: the GUI check. **Not verified: anything against a real
  controller.**

**First contact with the real VGC401, and the GUI on the lab computer** (the lab session, on the
lab computer, 2026-11-25, reported to me by message; its own record is its section "Seen on
hardware, lab session", which arrives with its first push. None of it seen by me):

- **The controller answers the probe** at 9600 baud: unit Torr, gauge head PCG (Pirani with
  capacitive sensor), firmware 302-519-D (the manual read is for 302-519-E), error word 0000,
  764 Torr at atmosphere.
- **One difference from the manual:** the pressure reply is `0, 7.6400E+02`, with a blank where
  the manual's form `x,sx.xxxxEsxx` has the sign of a positive value. The probe's pattern
  refused it and said "4 of 5"; corrected. The IOC's protocol file reads this form: the
  simulator now sends it and the device case passes (23). The IOC has not yet read the
  controller itself.
- **Reply times:** 91 to 112 ms per reply (one 20 ms), about 0.2 s for a request with its
  acknowledgement and data. The IOC's reply timeout was 150 ms (38 ms to spare) and is 300 ms
  now; the simulator answers after 95 ms. At that pace the device case showed a fault of the
  database: behind the four requests of the 2 s scan the pressure missed scans (5 requests a
  second instead of 6). The pressure request now has priority in the port's queue.
- **The rack IOC reads the controller** (the version before these changes): 764 torr without
  alarm, a new time stamp at every read, state, gauge head, unit, error word and firmware
  number valid, and the GUI on the lab computer shows the pressure. With it the GUI is seen
  to work against an IOC on another computer.
- **Verified by me after the changes:** the probe against its fake (5 of 5, and exit code 1
  for a silent one), the device case four times in a row (23 passed each), the simulators'
  tests (175), the plan check, the system tests (296 passed, 2 deselected, 797 s), and the
  GUI's stack started and stopped here with the corrected commands.
- **The first request of the first run was refused** (two NAK characters), every later one was
  answered, and the error word read 0000 right after. Not explained (P69).
- **The controller's own sending after power-on was not seen** in either run (P67).
- **GUI on the lab computer:** built in 18 minutes, the page opens with its eight tabs, every
  field says "no connection" because no IOC ran. `make dev-up` failed at its last step there:
  Ubuntu's Compose 2.40.3 refuses the project file unless the profile "build" is named. The
  Makefile and two helper scripts name it in every call now (the command the lab session used
  by hand on 2.40.3; here checked with Compose v5 only).

**First contact with the real TIC** (the lab session, on the lab computer, 2026-11-25, reported
to me by message; the replies are in `TIC.md`, "Seen on the lab's controller". None of it seen
by me):

- **The probe: 10 of 10, twice.** A TIC Turbo and Instrument Controller ("TIC100", software
  D39700640T), turbopump type "EXT75DX Pump", backing pump type "Mains Backing Pump", the APG
  on socket 1, sockets 2 and 3 empty. That answers question 23.
- **A fault of the protocol file, found by it:** the identity has a NUL byte after the serial
  number, and with it `TIC:ident:get` was INVALID at every read (reproduced with the simulator
  sending the same form). `tic.proto` now ignores what follows the identity's text.
- **What the IOC assumed about a measuring gauge holds for the APG** (A52): state "On", units
  type 59, the value in pascal while the display is in mbar (4.62e4 Pa at atmosphere before
  the owner's atmosphere adjustment of the gauge, exactly 1.0000e+05 Pa and "1000" on the
  display after it). A newly plugged gauge stays in "New Gauge Id" without a reading until it
  is accepted at the TIC's front panel.
- **Reply times** 23 to 86 ms: reply timeout 150 ms instead of 120 ms.
- The simulated TIC has the real identity's form and the cart's turbopump type.
- **One command was sent to the TIC, by hand and on the owner's word** ("can you start the
  roughing pump?"): the lab session sent `!C910 1`, the TIC answered `*C910 0`, and the
  backing pump reported the state On 4 s later; the turbopump stayed stopped. Nothing in the
  repository sends a command: probe, protocol file and database are queries only as before.
  So the manual's command form works on this controller (question 24).
- **The turbopump was started the same way** ("start the turbo when the pressure is low
  enough"): `!C904 1`, answered `*C904 0` after 19 ms, with the backing pump on and the gauge
  at 10 Pa. Seen in the probe's log every 5 s: state 5 "Accelerating" up to about 50 % speed,
  state 4 "Running" from there on (not from full speed), 100 % after two minutes; no
  "Starting Delay", alert and priority 0 throughout. The backing pump went from 0 to 4 with no
  state in between at that sampling.
- **The APG reports its floor as an ordinary reading:** exactly 1.0000e-02 Pa (1e-4 mbar,
  7.5e-5 torr) in the state On, with no alert, once the turbopump ran; the lowest value above
  it was 0.62 Pa. The IOC would show 7.5e-5 torr as valid (P72).
- **Verified by me after the changes:** the probe's self-test, the simulators' tests (175),
  the plan check, the TIC's device case (13 passed, three times), the system tests (296
  passed, 2 deselected, 797 s).
- **Not seen:** the IOC on this controller (the adapter hangs on the lab computer), a stop of
  either pump, a start of the turbopump with the backing pump off.

**The rack IOC reads the TIC** (the lab session from the lab computer, 2026-11-25, 15:06, after
the owner's pull and restart on the rack server; not seen by me): `TIC:ident:get`
"TIC100;D39700640T;160070509" (the identity fix works on the controller), variant TIC, the APG
on socket 1 at 750 torr in the state On, sockets 2 and 3 "Gauge Not connected" and INVALID,
turbopump Stopped at 0 %, backing pump Off, all without alarm. Over five minutes no reading
of seven watched PVs turned INVALID (the station was idle; P73 stays open for a running
station and for hours). The adapter's by-path name in `ports.real.cmd` is right; the rule for
`/dev/mist2/tic_station` passes `udevadm verify` and is not installed. The foreline pressure
from the VGC401 arrives every 0.8 to 1.2 s since the restart with the corrected database.

## Running

State of 2026-11-24, evening. Nothing is running. T23 to T27 are merged (see "Done"). The
table of the tasks ordered today:

| Task | What | Brief |
|---|---|---|
| T23 | The scan program: a Python program that runs a scan through Channel Access only | `briefs/T23-scan.md` |
| T24 | The dipole magnet supplies as PVs: a Python service for the NI USB-6001, `dipole.db` | `briefs/T24-daq-dipole.md` |
| T25 | The picoammeter as PVs, for an assumed model (A44) | `briefs/T25-picoammeter.md` |
| T26 | The system brought in line with the lab's files of 2026-11-24: the source supply's name, the Faraday cup, the flow meters, the sensor box out, names of the serial devices | `briefs/T26-lab-files-2026.md` |
| T27 | The three parts of the dipole scan together in one device case (ordered after their merge) | `briefs/T27-dipole-scan-together.md` |
| T28 | Firmware for an Opta in place of the lost interlock box, with a compile in a container and tests on a PC | `briefs/T28-interlock-opta.md` |

After the merges of T23, T24 and T25 I ran, on the merged head: the simulators' tests, the
three new device cases, both sets of unit tests and the plan check. The system suite was not
run: the merges changed no file of an IOC, no database in use, no test of the suite and
nothing of the simulator but a new module with its tests and a line of its README.

- T19 (P40) is merged, see "Done". After its merge only the system suite was run again, on
  the merged head. The GUI check, the device case and the hand check ran on the branch, whose
  databases, tests and GUI are the same files: the merge added the plan's revision number and
  this document.
- After the full runs on the merged tree two changes were merged: the fix of the loop's mode
  request (its test run alone, without and with the fix) and T17d (the logger's tests on its
  branch). On the final head the GUI check (exit 0, 289 checks; its note after the IOC start
  names two internal records only), the logger's tests (35 passed in 409 s) and the system
  suite (281 passed in 743 s, saved settings unchanged; run after plan 0.16 as the baseline for
  T19) pass in my runs.
- T20 (P45) is merged, see "Done". As with T19, after its merge only the plan check and the
  system suite were run again, on the merged head: the merge added the plan's revision number
  and this document to what I had run on the branch.
- T21 (P47) is merged, see "Done". After its merge the plan check and the system suite were
  run again on the merged head; the device case and the GUI check ran on the branch.
- T22 (P49) is merged, see "Done". After its merge the plan check and the system suite were
  run again on the merged head; the device case, the GUI check and the hand check ran on the
  branch. The merge added a corrected comment in the protocol files, a line in the
  simulator's README, the plan's revision and this document.
- 2026-11-24, after your answer 31: the branch is pushed. The clone and build commands of
  `LAB-SETUP.md` step 2 were run from the pushed branch in a fresh Ubuntu 24.04 container, and
  the rack IOC started there in `real` mode. After these changes (a comment in the two protocol
  files, documents, the build script) only the plan check ran; no database, record or test
  changed.
- 2026-11-24, later: plan 0.21 (hosts and notes only), registry and documents regenerated,
  plan check passed. No suite run: no record, database or test changed.
- Next: what the first day with hardware shows (`LAB-SETUP.md` section 7), your word on the
  dipole scan (question 17), and your comments on the drawings (answer 25).

## Open

- Turbopump 2 is not in the system in phase 1. Its records, simulator and tests stay, and the
  plan flags it as not installed, so the GUI does not draw it. Say so if the rack IOC should
  not load it at all.
- Two gauges you want to add are in the plan as planned devices only: foreline, gas injection.
- The dipole second cross, the emittance scanners and the new interlock system are out of scope.
- The dipole scan off LabVIEW (your wish of 2026-11-24, work package WP11) is not started:
  question 17.
- Worktrees and branches of the subagents (`emu/t*`) are still there, on this computer only:
  they were not pushed, because each is merged into `emulated-iocs`. They go when you have
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
| 23 | Setting values on the drawings (2026-11-22) | "On the main screen/tabs, all the PVs are read-only. Only if I click on it and the pop-up appears can I change a value. I would like to be able to set values in place on the main screen." | Changes the decision of gate G2 (the drawing was read-only). In brief T16 as requirement R10: set points and requests in the tags, saved settings stay in the device window, the vent valve still asks first. Built and merged on 2026-11-22 (T16) |
| 24 | Tabs as windows (2026-11-22) | "Would it be possible to pop out individual tabs as separate windows and re-attach them if the user wants to?" | Yes, as browser windows opened by a control on the tab (a browser cannot dock). In brief T16 as requirement R11. Built and merged on 2026-11-22 (T16) |
| 25 | Comments on the drawings (2026-11-22) | "The filament should be vertically centered, attached to the left wall of the plasma chamber and have its tip point to the right. Stuff like that. I have a number of them." | The geometry is data (`RAS/mist2/ReactApp/src/config/drawings.json`). I apply them myself after T16 is merged: your list first, then a session with the GUI open in your browser |
| 26 | The MFC's set point of -20 % (2026-11-23) | "That is correct behavior. The MFC accepts a minimum value of -20, which we use to ensure the 'most closed' state possible." | Closes my open point P41 (I had taken the -20 % after a start for a fault of the simulator). In the plan as a note of the MFC (revision 0.16). Nothing to change |
| 27 | The interlock gate's rare case, P45 (2026-11-23) | "Yes, fix P45. There will be a hardware interlock. The software state is just an extra layer plus information in the logger." | Answers question 13. Task T20 (brief `T20-permit-enforce.md`): while the permit is lost and a supply reports its output on, the off sequence is sent again. Kept simple, because the hardware interlock is the first line |
| 28 | The operator's direction of the same race, P47 (2026-11-23) | "Leave P47" | Answers question 14. Nothing is changed. P47 stays in the open points as a known behaviour with its way out (on, then off) |
| 29 | P47 once more (2026-11-23, a few minutes after answer 28) | "Sorry, no fix P47" | Read by me as a correction of answer 28: fix P47. Task T21 (brief `T21-switch-resend.md`). Not the remedy I had named (the gate evaluated through Channel Access): that one still loses a command when several follow each other within a millisecond. Instead a rule at the switching record itself: a value written into it while it was busy is sent when it is free |
| 30 | The late reply on the Matsusada lines, P49 (2026-11-23) | "Yes, fix P49" | Answers question 15. Task T22 (brief `T22-late-reply.md`). Two parts, the second added by me when I read the logs and the source for the brief: the line is kept quiet after a mismatch until the outstanding reply has arrived (what I had named to you), and every reading that carries a state or a setting first checks the unit number in a status reply, because at the first contact a stray reply would otherwise be copied into the next supply's request and set point. The monitors are left as they are; what that leaves open is measured and reported to you |
| 31 | The monitors, the push, the first day with hardware (2026-11-24) | "Leave them and commit/push everything. I'll be at the lab in about three hours and will install the new control system/check everything with real hardware. Send me concise instructions for the setup." | Answers question 16: the monitors stay unchecked (P51 is a known behaviour). `emulated-iocs` pushed to `origin` under its own name; no pull request, which you did not ask for. Instructions: `LAB-SETUP.md`, with `EPICS/ioc/host/build-epics.sh` |
| 32 | The state of the lab, the rack computer, the logger's home (2026-11-24) | "Nothing is running in the lab right now. We moved to a new location and everything was in storage for over a year. I expect to bring devices back online one by one. My plan, thus, is to copy the data from the rack computer then wipe it and do a fresh install of Ubuntu. Then install epics and the Matsusada driver, proto and db files according to your instructions as the first step. Where should the logger live? Main control computer? It has the most modern hardware, the largest disk and easiest to add more disks." | `LAB-SETUP.md` section 1 rewritten for it: what to save from Windows before the wipe (the lab IOC's folder, the list of adapters Windows remembers), a check of the CO-U32 from the installer stick before Windows is gone, Ubuntu 24.04. There is no lab IOC to protect or to ask for `dbl`. The logger: my answer is under question 11; it waits for the operating system of the main control computer |
| 33 | The main lab computer (2026-11-24) | "The main lab computer already runs ubuntu, so I can test the CO-U32 there, right?" | Yes. `LAB-SETUP.md` section 1: the adapter check is done there with the rule file itself, before the rack computer's Windows is wiped. It also settles the logger's home (question 11): the main lab computer, if it stays on whenever the IOCs are on. In the plan since revision 0.21 |
| 67 | Start and stop of the TIC's pumps from the GUI (2026-11-25, to the lab session) | "yes, I want to start and stop the pumps from the GUI." | Answers question 24, as the lab session reports your words; I have not had them from you here. **Task T32** (brief `T32-tic-pumps.md`), which starts when T31 is merged, because both change the same files and need the one emulation. My decisions in the brief: two requests only (backing pump, turbopump), each acknowledged by the TIC; the read-only database stays as it is and the requests live beside it; a restart of the IOC neither starts nor stops a pump; the IOC refuses a turbopump start without the backing pump and a backing pump stop under a running turbopump; no sequence, no gauge switching, no pressure condition; start and stop ask for confirmation in the GUI; the pumps are listed beside the drawing, not drawn into it. What the controller does after each command is taken from the lab session's record of today's starts and stops by hand. Open: question 26 |
| 66 | The gauge box, the AIM's socket and the rule for the AIM (2026-11-25, to the lab session) | "Yes, drop it" (the homemade gauge box), "Inficon, AIMs (receptacle 2 on the TIC) and APG are connected to the respective controllers. I still need to connect the comressed air and solenoid valve to one of the relays and get cooling water for the large Turbo (currently manually controlled).", and "The AIMs may not be turned on until the APG shows 1e-2 Torr or lower" | Answers question 25 a and b. **The homemade gauge box is out of the system**; taking it out of the rack IOC, the emulation, the plan's loads and the GUI is task T31 (brief `T31-gauges-on-the-tic.md`), which also puts the TIC's gauges 1 and 2 and the foreline gauge into the GUI's drawings and corrects the title and banner (P68). **The AIM is on socket 2** and reads "Off" at atmosphere with its pressure INVALID (lab session, through the rack IOC). **Your rule for the AIM is in the plan** (device `tic`): nothing in the control system switches the AIM, so nothing enforces it; the TIC can hold it by a setup of its own, and how yours is set has not been read. Not connected by what the IOC sees (lab session): the interlock Opta and the flow meters; the valve box answers with the new firmware |
| 65 | Where the gauges go: a change of plan (2026-11-25, to the lab session) | "slight change of plans: inficon foes on the roughing line (because it has a smaller flange than the others) and the APG and a regular AIM go on the 6-way. We defer the nAIM to later. both APG and AIM should be controlled by the TIC station" | In the plan (revision 0.34). **The six-way cross's two pressures come from the TIC now** (`TIC:gauge<n>:getpressure`): the APG is on socket 1, the AIM's socket is not known yet. **The nAIM is flagged not installed**: its records stay loaded and INVALID, the GUI does not draw it. The INFICON stays where it is in the plan (`PRESSURE:foreline:*`). I read "controlled by the TIC" as: the TIC supplies, switches and reads both gauges, and the IOC reads the TIC; the IOC switches no gauge. **Not done:** the GUI's two drawings still show the homemade gauge box's APG on the six-way cross and nothing of the TIC there (P66); the interlock table's sources are changed in words only. Open: question 25 |
| 64 | The TIC's adapter on the rack server (2026-11-25, a paste to the lab session) | The output of `udevadm` on the rack server for its four USB serial ports, with "ioc is restarted after pulling, but I didn't move the TIC over yet" before it | The rack IOC runs the corrected version since about 14:01; the lab session saw the foreline pressure's time stamp change every 0.8 to 1.2 s over 64 s (the priority works on the controller). **The TIC's adapter is on the rack server now**: `/dev/ttyUSB3`, Prolific, at `pci-0000:01:00.0-usb-0:4.4:1.0`, behind your USB extension, which is a hub. The lab session put that socket's by-path name into the TIC line of `ports.real.cmd` (its commit; the name is derived, not seen there). **By me:** the rack IOC started in a container here with that port file and finished its start (every port line taken, only missing devices in the log); a rule line for `/dev/mist2/tic_station` by the same socket in `99-mist2-serial.rules`, not tested. The port file keeps the by-path name until the rule file is installed there. The extension passed the lab session's load test on the lab computer (16210 queries, none lost; P73). Not seen: the IOC reading the TIC |
| 63 | The lab session's push, the station's shutdown, the name tic_station (2026-11-25, to the lab session) | "yes, push your commits and shut the TIC station down gracefully. I think tic_station is a good name. ad 3. will do, ad 4. yes ok." Before it, at the pump: "can you start the roughing pump?" and "start the turbo when the pressure is low enough" | **The lab session's record is in the repository** (its section "Seen on hardware, lab session", pushed with your yes). **The station was pumped down and shut down again through its serial line, by hand, each command on your word:** backing pump on, turbopump on (100 % after two minutes), then both off; four commands in all, every one acknowledged by the TIC. The repository's files still send no command. **tic_station** is the name of the station's serial line now (`/dev/mist2/tic_station` in the rack IOC's port file, as the lab session read your word); its Prolific adapter has no serial number, so the name needs a rule by the rack server's USB socket, which waits for that socket's name. The PVs stay `TIC:*`. "ad 3": you pull and restart the rack IOC yourself. "ad 4": the GUI's corrected start command was run on the lab computer and passes there. Open with you: question 24 (start and stop in the IOC) and P72 (the gauge's floor) |
| 62 | The Edwards station: a TIC cart for 115 V (2026-11-25, to the lab session) | With the foreline pressure on the screen: "I see the pressure in the CS. The Turbo stays manual until I have more time. Let's talk about the TIC next." Then "The station's part number is TSM1D1002 does it accept 230 V mains? Could the nAIM and the Inficon and the Edwards APG100-XM in theory be driven through that controller?", "it says 115 V in tiny letters at the inlet receptacle", and "It's front label says TIC and it has three RJ45 recepticals on the side" | **The foreline pressure is read on the real controller** (the lab session saw the PVs and the GUI; its section has the values). **The station's controller is a TIC with three gauge sockets** (owner), so T29 fits and stays loaded. The part number has the form of Edwards' "nEXT TIC Cart" order numbers, in which ...1002 is the 100 to 115 V version (read by the lab session in Edwards' webshop, not by me; this number itself is not listed, and it first read it as a T-Station and corrected that). **Mains: 115 V, not 230 V.** The TIC controller alone takes 90 to 264 V by its data sheet, so the 115 V belongs to something else on the cart, most likely the backing pump; the rating plate and the manual decide, and neither of us has read the manual. **The gauges:** the APG100-XM is an Edwards active gauge and goes on a TIC socket; the nAIM is a digital gauge with its own serial line and supply and stays on its own line; the INFICON head belongs to the VGC401. Not yet known: whether the 9-pin serial socket is there, what is plugged into the three sockets, which pumps the cart has (question 23 b to d). No probe has run |
| 61 | A session on the lab computer, and its first report (2026-11-25) | "ok, i installed claude desktop app on the lab computer and logged in", then "Ok, new session is in session (haha)" | **A second Claude session runs on the lab computer** ("INFICON VGC401 lab setup"); I can message it and it answers. What it reported, none of it seen by me: the rack server is **10.77.0.6** (the owner's word to it; it answers a ping, and no IOC runs there now). The VGC401 hangs on an FTDI FT232R adapter, serial number FTE7S80M, `/dev/ttyUSB0` on the lab computer; **the probe has not run**: the user `mist` is in no group that may open the port (the owner has the command). ModemManager runs on the lab computer and looked at the adapter; whether it sent anything is not known (P67). For the GUI the lab computer had neither Docker nor make; installed by the owner, with `docker-buildx`, which 26.04.1 does not install with `docker.io`. The lab computer has no GitHub login, so that session cannot push yet; its results come by message until then. **From it, by me:** a rule line for the adapter (`/dev/mist2/vgc401`, not tested), `docker-buildx` and the new login in `LAB-SETUP.md`, the addresses in the plan (revision 0.30) |
| 60 | SSH for the development session, and the lab computer (2026-11-25) | "Let's try setting up ssh-ing into the lab computer through the experiment intranet. The lab computer's IP is 10.77.0.1. You are connected and ssh is installed on the lab computer.", "I just switched the manual IP of the laptop to 10.77.0.2 to not interfer with the lab computer's 10.77.0.1", "I can ssh from WSL into 10.77.0.1 using the username and password of the lab computer", the output of `ip -4 -o addr show` there, and "I powered on the VGC401, attached the sensor and plugged it into the lab computer through a USB-to-RS232 adapter cable" | **The development session runs on the desktop PC, not on the laptop, and that PC is not on the lab's network:** it has an address from its own router only, and neither 10.77.0.1 nor 10.77.0.2 answers from it (seen from WSL and from Windows). The lab computer is `mist-at-iba`, user `mist`: 10.77.0.1/24 on `eno1` (the experiment's network), and a private address of the site's network by DHCP on a USB adapter, which is not reachable from outside either. So no SSH from here without a VPN into the site, which is a question for the site's IT and not for today. **My recommendation, given twice: Claude Code on the lab computer** (it needs outgoing internet only), with `CLAUDE.md` as its instructions; not yet answered. A key for the lab exists on the desktop (`~/.ssh/id_ed25519_mist2lab`); whether its line was added on the lab computer I do not know, and it is of no use without a network path. The VGC401 hangs on the lab computer for now: for the rack IOC its adapter must move to the rack server |
| 59 | The foreline gauge's controller (2026-11-25) | "The foreline pressure gauge is a inficon VGC401", then "It has a "control" male 9-pin sub D and an "RS232" female 9-pin sub-D receptacle in the back" | Answers the plan's question on the device `gauge_foreline` (make and model, how it is read): an INFICON VGC401 with an RS-232 socket. **Nothing in the IOC reads it yet: task T30** (brief `T30-inficon-vgc401.md`), read-only, with my decisions in the brief: the PV is `PRESSURE:foreline:getpressure` in torr, the name the plan had already proposed (the brief said `FORELINE:getpressure`; changed when the file was loaded, see the decisions), below and above the gauge's range the value stays with a MINOR alarm, every fault is INVALID. Into the plan when T30 is loaded into the rack IOC. Not known: which gauge head hangs on it, its baud rate and unit (the probe reads them), and the cable to the rack server |
| 58 | Today's goal: interlock, vacuum, pump the six-way cross (2026-11-25) | "For this week, we are good. My goal for today is to set up the interlock, the vacuum system, and start pumping on the 6-way cross only (no source). That requires setting up everything we need for the TP controller, the Edwards TIC station, and the foreline pressure reading as well as the ion gauge controller." | Closes the rail's current for now (answer 57). **What exists for today:** the interlock Opta's sketch (not yet run on the board), the gauge box (`PRESSURE:*`), the nAIM (`AIM:*`), the valve box (`VALVE:*`), the NT 20's data output (`TURBO1:raw:get`, format not known, P14). **What does not exist:** start and stop of the turbopump from the IOC (the Opta for it has no firmware, P13, and the three Optas in hand are taken), so the NT 20 is run at its front panel; and **an Edwards TIC is not in the plan at all**: task T29 (brief `T29-edwards-tic.md`), read-only, because I do not know what the station is. Asked: which TIC it is, what it runs, what hangs on its gauge sockets, and how it reaches the rack server (question 23) |
| 57 | The solenoid valves on the same rail (2026-11-25) | "Actually, we may be getting closer than I want: The solenoid valves require 3 W @ 24 V each. We have four (though only three are used at the same time)." | **3 W at 24 V is 0.125 A per valve**: 0.375 A with three on, 0.5 A with all four. With the three Optas at their most (0.275 A, answer 56): **0.65 A with three valves, 0.775 A with four, of 1.5 A**, so about half at the worst. With the two Optas still to come (valves, turbopumps): 0.83 A and 0.96 A. Not in these sums: the analog expansion, and anything else on the rail. I read the sentence as: the valves are fed from the crate's +24 V rail (A50). In the plan (revision 0.28). These are sums of rated values; a current measurement on the rail has not been made. Not known here: whether the valve coils have a diode across them, which matters on a rail shared with the Optas |
| 56 | What the crate's +24 V rail can give (2026-11-25) | "These crates are beefy with 1.5A maximum combined current on the +24 rail (2 A on +-24 V rails together, but I have no devices hanging off the -24 V rail)" | **1.5 A at most on the +24 V rail** (2 A for both 24 V rails together, nothing on the -24 V rail). The three Optas take 0.275 A at most (3 x 2.2 W at 24 V, data sheet), under a fifth of it; each further Opta adds up to 0.09 A. Not known here: what else hangs on the +24 V rail, and what the analog expansion (AFX00007) takes. In the plan (revision 0.27). Nothing to change |
| 55 | What feeds the Optas (2026-11-25) | "I think what you mean is that the OPTA needs an external power supply in addition to the USB from the computer that is how we have them set up anyway. They get power from the +24 V rail of an old NIM crate" | Yes, that is what I meant: USB alone does not power the relays (user manual). **The lab's Optas are fed from the +24 V rail of an old NIM crate and have USB to the computer**; the interlock Opta is wired the same way, and its door switches are fed from the same rail. In the plan (revision 0.26), `LAB-SETUP.md` and the sketch's README. What follows from it, not seen: with the crate off no input is high and no relay has power, so the doors read as open (or the box does not answer) and no AU or REK output can be switched on: the crate is part of the interlock. Three Optas take at most 0.3 A together (data sheet: up to 2.2 W each at 24 V); what the crate's rail can give: answer 56. For the bench check "24 V alone" the plus wire is taken off at the Opta, not the crate switched off |
| 54 | The third Opta becomes the interlock box (2026-11-24) | "Let's use the third OPTA, the dipole and quads will have to wait a but anyway. Yes, write a sketch for the OPTA." | Answers question 21 (the first part) and question 20: the third Opta is not used for the dipole supplies for now. Task T28 (brief `T28-interlock-opta.md`), with my decisions in the brief: USB serial as the old box, the old box's four channels in the same order (no PV and no database changes), inputs I1 and I2 for the doors, relays 1 and 2 on only while both doors are closed, a hold time of 1 s so that a short opening reaches the IOC, no latch in the Opta (as the old box; the IOC latches the supplies), a hardware watchdog, and a compile in a container. Not answered: whether the door switches and their cable are still there and which way they switch (A48) |
| 53 | The interlock box is missing (2026-11-24) | "I can test that tomorrow" (the IOC restart with relay 5 on, P60), then "I can't seem to find the interlock box. Should we appropriate an OPTA for that?" | **Without the box `interlock_open` stays INVALID and no AU or REK output can be switched on from the IOC.** My answer is yes, the third Opta, as question 21: it is free (answer 42), the job needs two of its eight inputs, and one of its relays can do what the old box did by itself with its two interlock outputs (on only while both door inputs are high; `InterlockBox.ino`, read again). With the same four channels (i1, i2, s1, s2) `interlockbox.db` and every PV name stay as they are. Its firmware does not exist. Nothing is built and the plan is unchanged until you decide; the stopgap is a spare Arduino Mega with the sketch of this branch |
| 52 | The relays, and what an IOC restart does to them (2026-11-24) | "It's an SRD-05VDC-SL-C and yes, it would be nice not to switch all Relais to zero when the ioc reboots" | **The relay type is in the plan** (revision 0.24): SRD-05VDC-SL-C, a 5 V coil by its type name, so the relay board's own supply is 5 V unless the board carries a regulator (not seen by me). **The requirement is recorded: an IOC restart must not release the relays.** Nothing had to be built for it, for two reasons. The IOC sends nothing to the box at its start (`first_contact.db`, checked in the emulation since T18). And the only other cause, a restart of the Arduino Mega when its port is opened, needs the DTR line to go from off to on: asyn opens a serial port with hang-up-on-close off (`drvAsynSerialPort.c`, read in the IOC image), so DTR stays on when the IOC ends and the next start makes no edge. Seen by me: with the IOC binary on a pseudo-terminal, the flag is on before and off after the IOC had the port. **Not seen: the box itself** (P60), and you have not said whether a relay was seen to drop. What still releases the relays: the first open after the box was plugged in or the server booted, and the Arduino IDE on that port. A warm reboot of the server would need the automatic reset disabled on the board; not done |
| 51 | The valve box switches (2026-11-24) | "The cable powering the relay board came off. Is that 5 V?", then "now I can hear it" | **The valve box works from the IOC to the relay:** with the relay board's supply cable back on (it had come off in transport), relay 5 switches on a `caput VALVE:s5:set`. The supply voltage of the relay board is not recorded anywhere in the repository; I did not name one, and asked for the relay type for the plan. Still to see: whether the box restarts, and releases its relays, when the IOC starts |
| 50 | A valve command through the IOC, seen; the relay does not click (2026-11-24) | "it's not switching. I held my ear very close - no sound", "The get always shows what I set earlier", and `caget -a`: `VALVE:s5:set` 1, `VALVE:s5:get` 1, no alarm | **The acknowledged set works on hardware:** the box answered "ok" (no alarm on the set record) and reports its pin for channel 5 as switched. The read-back is the Arduino's own output pin, so it says nothing about the relay. That no relay clicks is on the box's relay side, to be found by you: the relays' own supply, a relay on channel 5 at all (the channel is unused), or relays that switch without a sound. The new sketch has the pins and the switching logic of the lab's old one (compared with the copy from the rack computer). The serial monitor check after flashing was skipped; the identity read by the IOC stands in for it |
| 49 | The valve box with the new firmware on the IOC (2026-11-24) | "Ok, the valve box is flashed and USB-attached to the IOC", then the output of `caget -a`: `VALVE:id` SolenoidValveBox, `VALVE:firmware` Nov 24 2026, `VALVE:s1:get` 0, `VALVE:s5:get` 0, no alarm; `caput VALVE:s5:set 1` (Old 0, New 1); "How do I know it switched? I didn't hear it" | **The first board with libcom1 protocol 2 answers the new IOC:** identity and firmware date are read, the valve states are valid. So the sketch of this branch compiles and uploads with the Arduino IDE on Windows, and the name by serial number (`/dev/mist2/valves`, `99-mist2-serial.rules`) works, since the IOC opens the box under that name. Not seen yet: the read-back after the set, whether a relay switches (channel 5 may have no relay, or the box's own supply for the relays may be off: USB feeds only the Arduino), and whether the box restarts at an IOC start |
| 48 | The limits of all four supplies, seen; the valve box is flashed from a Windows 11 laptop (2026-11-24) | "I'll flash it from my laptop (win11)", and the output of `caget -a`: `AU-20P15-1:current:limit` 15, `AU-20P7-2:current:limit` 7.5, `AU-20P7-4:current:limit` 7.5 (all with the time of the IOC start, 18:00:04), `AU-20P7-3:current:get` 7.5 and `AU-20P7-3:voltage:get` 0 (time 18:16:59, 17 minutes later), none with an alarm | The first contact ran through for all four supplies: each got its limit from `limits.defaults` and confirmed it. The periodic reads of the settings (every 5 s) still work 17 minutes after the start: the supplies stayed under remote control and the lines are in step. Not seen: the IOC's log, the update rates, any switching or voltage setting. The valve box's flashing steps for Windows are in my answer (the sketchbook's `libraries` folder, an old `libcom1` there removed first); not in `LAB-SETUP.md` |
| 47 | The IOC on the four supplies, seen (2026-11-24) | The output of two `caget -a` commands on the rack server, with the new IOC running: `AU-20P15-1`, `AU-20P7-2`, `-3`, `-4` `status:read` OFF without alarm; `AU-20P7-3:voltage:read` 4.884; `AU-20P7-3:current:limit` 7.5 (time 18:00:04.3); `AU-20P7-3:voltage:setpoint` 0 (18:00:04.5); `interlock_open` 1 LINK INVALID | **The new IOC talks to the real supplies.** All four are read (output off, remote control, no alarm). For unit 3 the first contact ran through: the current limit of `limits.defaults` was sent and its read-back compared without alarm, and the voltage set point was taken over (0). The monitor shows one count of its 12 bits (4.884 V). That limit record without alarm also answers the open point of answer 45: the supply accepts commands that follow each other without a pause (`CH1`, `STS`, `CH1?`; and `REN`, `STS`, `SW?` at the first contact). `interlock_open` is INVALID as expected, the interlock box is not connected. Not seen: the limits and set points of the other three, the IOC's log lines of the two lines, the update rates, any switching or voltage setting |
| 46 | The IOC on the supplies, and the valve box next (2026-11-24) | "I installed EPICS before we worked on the usb ports for these devices. DO I have to compile it again?", then "OK, seems to work.", then "Next, lets add the solenoid valve controller. I think I have to update the firmware? I already installed Arduino IDE" | No rebuild: nothing compiled changed since the first push (checked with git). **"Seems to work" is not recorded as verified:** I asked for the output of two `caget` commands and for the IOC's lines on the two Matsusada ports, and have not seen them; whether the supplies take two commands in a row without a pause is still open. The valve box: yes, its firmware must be the protocol 2 sketch of this branch, or every valve command is refused. I compiled that sketch and the interlock box's for the Arduino Mega 2560 (exit 0; 10.1 and 10.5 kB of flash). The flashing steps are in `LAB-SETUP.md`. Not flashed, not tried on the box |
| 45 | The supplies under remote control (2026-11-24) | The output of `ls -l /dev/mist2/` and of the probe with `--remote` on both adapters; "I did not power on the fifth unit since we don't need Lens 3 at the moment. Can I connect them to the power supplies? Without any HV cables attached ofc." | **The names by USB socket work** (`/dev/mist2/co-u32 -> ttyUSB0`, `usb-opt -> ttyUSB1`). **Under remote control all four supplies answer all six queries in the form the protocol files expect** (`#3 CF RM`, `SW0`, `CH0=0000H`, `CH1=0000H`, the monitors), and `GTL` gives them back to the front panel (`CF LO`). So the settings are answered under remote control and not under local control (A24, P59). Reply times 16 to 32 ms. The stored current limit of each supply is 0. Read by me as the question whether the IOC may now talk to the four supplies: yes, and what its start sends is in my answer (REN, the status and setting queries, and the current limit of `limits.defaults`). Whether the supplies take two commands that follow each other without a pause, as the protocol files send them, is not shown yet: the probe waits 0.2 s after REN |
| 44 | The supplies answer: the probe on both adapters (2026-11-24) | The output of `ls -l /dev/serial/by-path/`, `groups` and the probe with units 1 to 5 on `/dev/ttyUSB0` and `/dev/ttyUSB1` | **Units and lines:** units 3 and 4 answer on socket 1.2 (`ttyUSB0`), units 1 and 2 on socket 1.1 (`ttyUSB1`), no unit 5 anywhere: as you said on 2026-11-21 (answers question 18 a). **The status reply is as the protocol files check it:** `#3 CF LO` (A41 confirmed for the form; under local control). **Reply times:** a reply is complete 31 to 35 ms after the request, median 32 ms; with 17 to 19 ms of characters on the line that is a turnaround of about 15 ms, the FTDI chip's latency timer (A6: the 16 ms case, not the 5 ms one). **New, and against A24:** under local control the supplies answer `STS`, `MN1` and `MN2`, and do **not** answer `SW?`, `CH0?` and `CH1?`. Whether they answer those under remote control is the next test (the probe's new option `--remote`: REN before, GTL after). Done for it: the rule file names both adapters by their USB socket (`/dev/mist2/co-u32`, `/dev/mist2/usb-opt`; syntax checked, not tested), the probe has `--remote` (tried on a pseudo terminal that behaves as the supplies did) |
| 43 | The Matsusada adapters on the rack server, the first result on hardware (2026-11-24) | "Not yet, let's test the Matsusada communicators first", with the output of `lsusb -d 1192: ; ls -l /dev/mist2/ /dev/serial/by-id/` on the rack server (Ubuntu 26.04.1): two devices `1192:1000 MATSUSADA PRECIS CO Series`, no `/dev/mist2/`, and one name under `by-id`, `usb-MATSUSADA_PRECIS_CO_Series-if00-port0 -> ../../ttyUSB1` | **The Linux route works for the first step:** both adapters report the USB ID `1192:1000`, and the kernel's FTDI driver has taken them (a serial device exists), with the rule file's first rule. **No serial number over USB,** as the Windows list suggested: both adapters get the same name under `by-id`, so only one link is there, and the rule by serial number (`/dev/mist2/co-u32`) does not match. They are named by their USB socket (`/dev/serial/by-path/`). Not yet shown: that the supplies answer through them (the probe is next). The firmware for the third Opta (question 20): not yet, your word. The probe itself was run by me on the Python 3.14 of 26.04 against a pseudo terminal with canned replies |
| 42 | The Optas in hand (2026-11-24) | "Currently, I have three OPTAs (not lite, not wifi) and one AFX00007 extension module. How should I set them up until I can order more (if needed)" | In the plan (work package WP6, revision 0.23). My proposal is question 20; nothing is built for it |
| 41 | The computers as installed (2026-11-24) | "I ended up installing ubuntu 26.04.1 on both the main lab computer and the rack server. The small platform computer will stay on its older 32 bit linux. I also didn't install the server version." | **The build script failed on 26.04** (its compiler, GCC 15, takes C as C23, and StreamDevice 2.8.26 does not compile so): fixed with a compiler flag for that one module, sources unchanged, and pushed the same hour. Run in fresh containers: Ubuntu 26.04.1, 24.04, and 32-bit Ubuntu 16.04 and 18.04 (for the platform computer; 16.04 needed a second fix, its git is too old for one option), each with both IOCs started in `real` mode. `run-ioc.sh` finds a 32-bit build by itself. `LAB-SETUP.md` has what a desktop installation needs (SSH, tmux, no sleep, ModemManager off) and where the loop service runs if the platform computer's Python is older than 3.8 (the rack server). Plan 0.23. Checked in a 26.04 container: both rule files, the USB serial drivers in the standard kernel package, pyepics and the unit tests of the three Python programs on Python 3.14, Docker in Ubuntu's own packages |
| 40 | An overflow of the picoammeter in a dipole scan, question 19 (2026-11-24) | "End the scan" | As shipped: the picoammeter stays `required: true` in `scans/config/dipole.yaml`. Noted there and in `SCAN.md` as your decision. Nothing else changed |
| 39 | The rack computer's files, read (2026-11-24) | "download complete": the folder in your Dropbox, 6389 files, copied complete (none empty). What matters of it is in `reference/lab-2026/` with a README | **Agrees with this system:** 57 PV names of the lab's rack IOC with their record types; the line settings of gauge controller (115200, even parity), interlock box, valve box, nAIM, MFC and the Matsusada lines; the MFC at address 254 and 9600 baud; the scaling of the 15 mA supply (16-bit set, 12-bit monitor). All database and protocol files but four are identical to the snapshot of 2023. **Differs, and is being brought in line (task T26):** the source supply is `AU-20P15-1` in the lab, `AU-20P7-1` here; the Faraday cup is `FC1` with two values on a USB serial line, here `FC` with one value over TCP; five flow meters `FLOW:f1:getflow` to `f5` on an Opta (litres per minute by the sketch's arithmetic) replace the sensor box, which the lab's `st.cmd` no longer loads. **Differs from your answer 12, left as you said:** the lab's `st.cmd` has units 2, 3, 4 on one Matsusada line and 1, 5 on the other, with unit 4 as "Lens 3" and unit 5 as "Lens 2"; you said 1, 2 and 3, 4, with unit 4 as lens 2 (question 18). **Firmware:** the Arduino library on the rack computer is libcom1 without protocol 2, so the boards as last flashed give readings and neither identity nor acknowledged sets; the three sketches changed locally on the rack computer are in this branch with the same pins; the flow meter sketch was an untracked file there and is now in `reference/lab-2026`; no sketch of the Faraday cup Opta was found. **The 50 GB log** is the previous control system's (Python) list of exceptions from 2020-07 to 2022-02, no measured values: not worth keeping. **Not in these files:** the platform IOC (TDK, REK, thermocouples), so A7 to A9 stay open |
| 38 | The rack computer's files, first reading (2026-11-24) | The folder in your Dropbox, complete ("now it's done"); the rack computer is a Dell PowerEdge R210 | Read so far: the top-level files only (the folder itself was still being fetched; you asked me to wait). **The device list:** three devices `1192:1000` "MATSUSADA PRECISION USB MODULE" (COM7, COM9, COM15), each under an instance name made from the USB socket, not from a serial number: the Matsusada adapters report no serial number over USB as Windows sees them, so the udev rule's name by serial number (`CO001144`) will not work and `LAB-SETUP.md` now names them by socket (`/dev/serial/by-path/`); to be confirmed under Linux. FTDI adapters with serial numbers on COM8 (`A5051Z0G`) and COM13/COM14 (`FTJRNRWQ`); Prolific adapters without serial number on COM3, COM4, COM19; five Arduino Mega 2560 (COM5, COM10, COM11, COM12 with serial numbers, COM20 without); a Teensy on COM6 (serial `3596460`); Arduino Micro on COM22 and COM24; four more Arduino boards with the IDs `2341:0164` and `2341:0364`. **`some_notes.txt` (2022):** Mega no parity, Teensy even parity (as A10 has it); COM13 MFC, COM8 TDK, COM3 AIM, COM19 REK, COM22 thermocouples (so TDK, REK and thermocouples were on this computer then); "t2 = back plate, t4 = magnet plate", which differs from your answer 4. **`start_epics.bat`:** the IOC is `C:\EPICS\IOCs\sampleIOC`, built with MinGW. **`epics_error.txt` (2022-08):** record names `tdk:...` and `thm:data` in lower case, `REK-1:...` as today. The databases and `st.cmd` are not read yet |
| 37 | The adapters' serial numbers, and the files of the rack computer (2026-11-24) | "The USB-OPT S/N is 024152MP, The CO-U32 S/N is confirmed from the sticker to be CO001144", and: everything copied from the rack computer is in your Dropbox, folder `MIST-1 Lab/2026_Copied_from_rack_PC` (the EPICS folder with the protocol and database files, an Arduino folder, the head and tail of the log, the list of devices Windows remembers) | The CO-U32's serial number is confirmed from its sticker (A29; its USB ID is still to be seen). The USB-OPT's is known from its sticker (P34): whether the adapter reports the same text over USB, and under which USB ID, the device list will show; its rule line is added then. The files: not read yet, Dropbox was still delivering them when I looked. To be compared with A1, A4, A7 to A12 when they are complete |
| 36 | The rack computer before the wipe (2026-11-24) | A picture of its downloads folder, "a 49 GB text file with server logs, which I believe are from EPICS. Is it worth copying those?", and "The main EPICS folder on C: is only 87 MB, I'm copying it right now." | Seen in the picture: `base-3.15.8.tar.gz` (2022), so the lab's IOC was probably built on EPICS base 3.15.8; the folders `CDM v2.12.28 WHQL Certified` (FTDI's driver) and `PL2303_Prolific_DriverInstaller_v1190` (2018), so adapters with FTDI and with Prolific chips were probably in use, and a Prolific adapter often carries no serial number (then its name comes from `/dev/serial/by-path/`); a folder `Matsusada-CO` (2018). An installer in a folder is not proof of use: the list of adapters Windows remembers (`LAB-SETUP.md` section 1) is. My advice on the log: not the 49 GB, but its first and last lines and its dates, then decide; an IOC's log holds messages, not measured values |
| 35 | The dipole scan, question 17 (2026-11-24) | "Start now" | Tasks T23, T24 and T25, three engineers in parallel. What I told you before your answer: a simulated magnet supply and picoammeter, their records, and the scan program, tested in the emulation, with the unknowns as configuration values |
| 34 | The lab computer and the dipole scan (2026-11-24) | "Same computer and I want to move the dipole scan off LabView and into the control system or a standalone python script" | The plan's lab computer is the Ubuntu computer: host entry corrected (revision 0.21). The dipole scan is work package WP11 of phase 2, which already says: devices as PVs, the scan as a Python tool that only talks to PVs. Noted there with my proposal (both, in that split). Not started: question 17 |

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
   it is more to install. The first is built (T17, see "Done"), as announced.
10. The loop's settings that are not yours (A30 to A35): set point maximum 23 A, filament
    current between 80 and 90 A, at most 1 A/s, hand-back times, the 5 s Channel Access
    timeout of the platform IOC. And the Ubuntu version of the mini PC (`lsb_release -a`).
11. The logger: is the tier of each PV group right (table in `LOGGER.md` section 1, A36), and
    are about 370 GB of disk after two years acceptable (A37)? And on which computer should it
    run (lab computer, rack computer, a small server)? What it needs is in `LOGGER.md`
    section 10. You propose the main control computer (answer 32: the most modern hardware,
    the largest disk, the easiest to extend). My answer of 2026-11-24: yes, if that computer
    runs Linux itself and stays on whenever the IOCs are on. What decides is not its power
    (the logger and its database took 2 % of one core and 0.6 GB in the emulation) but that
    nothing is recorded while the logger's computer is off, asleep or restarting, and that
    the database needs a Linux with Docker. On Windows it would run inside WSL2, which stops
    with the session and with every Windows restart, keeps its data in one virtual disk file,
    and does not simply use an added disk. If the main control computer is the Windows PC of
    the plan and stays Windows: the rack computer first (fresh Ubuntu, always on with its
    IOC), Grafana opened from the control computer over the network (`MIST2LOG_BIND`), and a
    move later as `LOGGER.md` section 10 describes. Answered on 2026-11-24 (answer 33): it
    runs Ubuntu. So the logger goes to the main lab computer, with its automatic suspend
    off. It is the plan's lab computer (answer 34); the plan's entry is corrected.
12. With values set in place, a filament current typed into the supply's tag while the loop
    is in PID takes the source to MANUAL at once (the loop reports "written by someone else").
    Should the supply's tag mark that the loop holds this set point while in PID, or refuse
    the entry?
13. Answered on 2026-11-23 (answer 27): fix P45; the supplies will have a hardware interlock.
14. Answered on 2026-11-23: first "leave it" (answer 28), then corrected to "fix it" (answer 29). Task T21.
15. Answered on 2026-11-23 (answer 30): fix P49. Task T22.
16. P51: after one late reply a voltage or current monitor can still show a neighbour's value
    of the same kind for one cycle (0.15 to 0.2 s with two supplies on a line), without alarm.
    The same check as for the state reads would close it and halve the monitors' rate (4.6 Hz
    instead of 9 with two supplies). Shall the monitors be checked too? My recommendation:
    leave them as they are. It takes a reply more than 200 ms late, the value is replaced at
    the next cycle, and nothing acts on the AU monitors; the discharge loop reads the REK,
    which is alone on its line and cannot take a neighbour's value. Answered on 2026-11-24
    (answer 31): leave them.
17. The dipole scan (answer 34). Answered on 2026-11-24 (answer 35): start now. The facts
    below are still needed. The question was: shall I start on it now, in the emulation, or
    after the first days with hardware? It needs no hardware to start: a simulated magnet supply and
    picoammeter, their records, and the scan as a Python program that talks to PVs only, as
    the loop service does. What I need from you for it: the LabVIEW program (the VI, or
    pictures of its front panel and diagram: ranges, step, settling time, what it saves); the
    model of the Keithley picoammeter; how the NI USB-6001 is wired to the magnet supplies
    (channels, volts per ampere); and whether LabVIEW runs on the Ubuntu lab computer today,
    which would mean NI's Linux driver already serves the USB-6001 there.
    More from the three tasks: (a) the picoammeter: its model (type plate or its answer to
    `*IDN?`), what sits between it and the computer (the plan says RS-485, the 6485 has
    RS-232), its line settings, and what the LabVIEW program sets (zero check, range,
    integration time); (b) the magnet supplies: how many, amperes per volt for the program
    input and for the monitor, the current range, an enable input, whether they need slow
    changes; whether the NI box's power-on glitch (-7 V for 10 microseconds, its data sheet)
    is acceptable at the program input; on a lost IOC hold the current (as built) or ramp to
    zero; (c) the scan: range, step, settling and dwell of the LabVIEW scan, what it saves,
    and conditions that must hold during a scan; (d) which computer's IOC serves the dipole.
18. From the lab's files (answer 39). (a) Answered by the probe on 2026-11-24 (answer 44):
    units 1 and 2 on one adapter, 3 and 4 on the other, no unit 5. The question was: which
    UNIT number does the lens 2 supply have: 4, as
    you said on 2026-11-21, or 5, as the lab's `st.cmd` has it (there unit 4 is "Lens 3")? And
    which supplies hang on which adapter now? (b) What are the two values of the Faraday cup
    Opta, `FC1:i1` and `FC1:i2`, and in which unit? Is its sketch somewhere? (c) Which cooling
    circuit is each of the five flow meters? (d) Your notes of 2022 say thermocouple "t2 =
    back plate, t4 = magnet plate"; on 2026-11-21 you said 1 back plate, 2 filament
    feedthrough, 3 and 4 isolation transformers. I kept the later answer. (e) The platform
    computer's `st.cmd` and databases (TDK, REK, thermocouples) are still wanted. (f) Does
    the MFC send a carriage return after `;FF`? The lab's protocol file expects one, ours
    works with and without. (g) Are the flow meters 1260 pulses per litre, as the sketch
    says, and which make are they?
19. The dipole scan as shipped ends when the picoammeter overflows on a fixed range (the
    detector is "required"). The other way is to record those points as missing and go on.
    Which do you want? With automatic ranging, the state after power-on, it does not arise.
    Answered on 2026-11-24 (answer 40): end the scan.
20. The three Optas and the analog expansion (answer 42). My proposal until more arrive: the
    two Optas that are flashed stay as they are (flow meters, Faraday cup). The third Opta
    gets the analog expansion and takes the analog jobs: the dipole magnet supplies (program
    voltage out, monitor in), in place of the NI USB-6001, whose Linux driver is doubtful
    (P56), and the two gauges you want to add (foreline, gas injection) if their 0 to 10 V
    signals can be brought there. The turbopump stays at its front panel and the valves on
    the Arduino box until one more Opta and a relay expansion are there. Its firmware does
    not exist and would have to be written (libcom1 over Ethernet; the IOC side of the
    dipole, `dipole.db`, stays as built). Not checked by me: the expansion's output range and
    resolution (Arduino's page says voltage or current; the data sheet has the numbers).
    Shall I have that firmware written?
21. The interlock box is not found (answer 53). My proposal: the third Opta takes its place.
    The two door switches go to two of its inputs, each fed from the Opta's supply, so that a
    broken wire reads as an open door. It answers with the old box's four channels (i1, i2,
    s1, s2), so `interlockbox.db` and the names `INTLK:i1:get_interlock`,
    `INTLK:i2:get_interlock` and `interlock_open` stay. One relay is on only while both doors
    are closed, decided in the Opta without the IOC: a contact for the hardware interlock you
    said will come (answer 27). The old box did the same with its two interlock outputs.
    What it costs: the firmware has to be written, and libcom1 protocol 2 has not been
    compiled for an Opta here (the lab's flow meter sketch shows the older libcom1 running on
    one). I can have it written and compiled; its first run is on your bench. Not checked by
    me: the Opta's input voltage range against its data sheet. Question 20 stays possible:
    the analog expansion brings its own terminals, so the same Opta could take the dipole
    supplies later, at the price that every new flash opens the interlock for a moment.
    Not on the flow meter Opta, although three of its inputs are free: it is in use as flashed.
    The stopgap: a spare Arduino Mega with `AVR/devices/InterlockBox` runs today's sketch as
    it is (switches on pins 2 and 3, high = door closed, a pull-down resistor on each pin; its
    serial number goes into `99-mist2-serial.rules`).
    Neither an Opta nor an Arduino is personnel protection: for that the door switches have
    to break the supplies' own interlock input or their mains (layer A of the plan).
    Answered by answer 54: yes, and the firmware is written (T28). Still open: are the two
    door switches and their cable to the rack still there, and do they close when the door
    closes (A48)?
22. The Opta's interlock contacts, relays 1 and 2 (T28). (a) Must the contact itself latch,
    that is stay open after a door was opened until someone resets it, or is the IOC's latch of
    the supplies enough? Nothing is built for a latch. (b) What will the contacts switch, at
    which voltage and current? The Opta's relays need at least 300 mW (12.5 mA at 24 V); an
    interlock input of a supply that carries a few milliamperes needs a small signal relay in
    between (P63). (c) A new flash opens the contacts until the new sketch has run for 1 s. Is
    that acceptable?

23. **The Edwards TIC station (2026-11-25).** Asked with answer 58, not answered:
    a. What does its label say: TIC Instrument Controller, TIC Turbo Controller, TIC Turbo and
       Instrument Controller, or a pumping station (a cart with a pump set) with a TIC on it?
    b. Which pumps does it run, and is it the backing station of the big turbopump?
    c. Which gauge hangs on which of its gauge sockets?
    d. How does its serial port reach the rack server (which adapter)?
    Until then T29 reads every socket and both pumps and commands nothing.
    **Answered on 2026-11-25** by the owner and the probe (lab session): a) a TIC Turbo and
    Instrument Controller, "TIC100", on a pump cart TSM1D1002 for 115 V; b) turbopump type
    "EXT75DX Pump" and a mains backing pump, both of the cart; whether it backs the big
    turbopump is not said; c) the APG on socket 1, sockets 2 and 3 empty; d) a Prolific USB
    adapter without a serial number, on the lab computer for the test.

24. **Start and stop of the TIC's pumps from the IOC (2026-11-25).** You had the lab session
    start the backing pump by hand through the TIC's serial line. Do you want that in the IOC
    and the GUI: the backing pump and the turbopump of the cart, each with a start and stop
    request that the TIC acknowledges, a read-back from its state, and the request taking
    over the pump's state at an IOC start without sending anything (as the valves do)? Not
    built until you say so; T29 is read only by decision.

## Seen on hardware, lab session

Written by the lab session on the lab computer `mist-at-iba` (`CLAUDE.md`, "Two sessions"). "I"
in this section is the lab session. Newest first.

### 2026-11-25: the valve box switches from the control system (seen in the watch log)

Not asked for and not done by me: I set nothing. The `camonitor` log that runs on the lab
computer since 15:38:50 (gauges, the TIC's pumps, `VALVE:s1:get` to `VALVE:s4:get`) shows the
four used channels of the valve box switched on and off, one at a time, between 16:04:31 and
16:06:30 local time; the owner at work, I take it (he was wiring a solenoid valve to a relay).

- **Seen on hardware:** `VALVE:s3:get` 1 at 16:04:31 and 0 at 16:04:32; `s2` 1 at 16:04:34, 0 at
  16:04:35; `s1` 1 at 16:04:36, 0 at 16:04:37; `s4` 1 at 16:04:46, 0 at 16:04:47; then `s4`
  twice more, `s1`, `s3`, `s2`, each on for 1 to 4 s; all four 0 since 16:06:30.
  `VALVE:s2:set` carries the time stamp of the last of them (16:06:29).
- **So the box carries out sets from the IOC and its read-back follows**, with the sketch of
  this branch (`VALVE:id` `SolenoidValveBox`, `VALVE:firmware` `Nov 24 2026`). Which relay moved
  what at the bench is the owner's to say.
- In the same log nothing else changed up to 16:30: gauge 1 750.062 `On`, gauge 2 `Off`, both
  pumps of the TIC off, the foreline gauge 763 with "Measurement data okay".

### 2026-11-25: the owner wants to start and stop the TIC's pumps from the GUI (question 24)

Owner, 16:10, after I had told him that the TIC is read only in the control system and that
question 24 was open: **"yes, I want to start and stop the pumps from the GUI."** Nothing is
built by it; the development session's task.

What today's runs on the controller give that task, all above in this section: `!C910 1` and
`!C910 0`, `!C904 1` and `!C904 0` are each answered `*C9xx 0` within 19 ms; the backing pump
goes 0 to 4 and 4 to 0 with no state between seen at 5 s; the turbopump goes 0, 5 (to 50 %),
4 on the way up and 4, 7, 0 on the way down in 105 s; the state right after a command is still
the old one; the pump vents itself from the stop on (`?S853` = 1), so the stop order of its
manual held: turbopump stop, backing pump off right after. Not tried: `!C904 1` with the
backing pump off, a start with the turbopump still running down, any command with the IOC on
the line at the same time.

Asked of the owner with it: whether the AIM is to be switched from the GUI as well, or by the
TIC alone (his rule: not before the APG shows 1e-2 torr or lower). **His answer, 16:20:** "The
APG and the AIMs from the TIC cart should show as on the side flange. Does the TIC switch it on
automatically or would I go and do it from the panel? If the latter, definitely through the GUI
too."

- **For the drawing:** the TIC's APG and AIM both on the side flange of the six-way cross.
- **For the AIM's switching:** he wants it from the GUI unless the TIC switches it by itself.
  Which of the two holds on his TIC is not known: the serial manual gives each gauge a slave
  setup (a master gauge with an on and an off set point and an enable, config type 4), so the
  TIC can do it once that is set; how socket 2 is set is not read (the rack IOC holds the line
  and `tic.db` does not ask `?S914 4`), and the TIC's instruction manual could not be fetched
  (two copies answered 403). The turbopump's slave setup on this TIC read "no master, not
  enabled" today, which is all I have on how it was left. The log that runs on the lab computer
  shows it at the next pump-down: socket 2 going from Off to On by itself, or not.

### 2026-11-25: the AIM on the TIC's socket 2; a look at the whole rack IOC

Owner: "Inficon, AIMs (receptacle 2 on the TIC) and APG are connected to the respective
controllers. I still need to connect the comressed air and solenoid valve to one of the relays
and get cooling water for the large Turbo (currently manually controlled)." **Question 25 b is
answered by it: the AIM is on socket 2.**

**Seen on hardware, from the lab computer at 15:34:50** (`caget -a`, `IOC-RACK:heartbeat` 1737):

| PV | Value | Alarm |
|---|---|---|
| `PRESSURE:foreline:getpressure`, `:getstate` | 763, `Measurement data okay` | none |
| `TIC:gauge1:getpressure`, `:state:get`, `:alert:get` | 750.062, `On`, 0 | none |
| `TIC:gauge2:getpressure` | nan | LINK INVALID |
| `TIC:gauge2:state:get`, `:units:get`, `:alert:get`, `:priority:get` | `Off`, `PRESSURE (Pa)`, 0, `OK` | none |
| `TIC:gauge3:state:get` | `Gauge Not connected` | none |
| `TIC:turbo:state:get`, `:speed:get`, `TIC:backing:state:get` | `Stopped`, 0, `Off` | none |
| `VALVE:id`, `VALVE:firmware` | `SolenoidValveBox`, `Nov 24 2026` | none |
| `VALVE:s1:get` to `VALVE:s5:get` | 0 each | none |
| `INTLK:id` | | COMM INVALID |
| `interlock_open` | 1 | LINK INVALID |
| `FLOW:f1:getflow` to `FLOW:f5:getflow` | 0 each | LINK INVALID |
| `TURBO1:raw:get` | | DISABLE INVALID |

- **The AIM is known to the TIC and off:** socket 2 reports the state `Off`, not "New Gauge Id"
  and not "Gauge Not connected", with everything at atmosphere. Its pressure is INVALID in the
  IOC until the TIC reports it `On`, as `tic.db` is written. Whether the TIC switches it on by
  itself at low pressure or waits for the panel is not seen yet.
- **The owner's rule for the AIM** (15:40): "The AIMs may not be turned on until the APG shows
  1e-2 Torr or lower". 1e-2 torr is 1.33 Pa on the TIC's line. Nothing enforces it in the
  control system: the IOC switches no gauge. The TIC can do it itself, by its serial manual
  (D397-30-880 Table 1, object 913 and so 914, the "slave setup", config type 4): a gauge can
  have a master (gauge 1, 2, 3 or the turbopump's speed) with an on set point and an off set
  point in pascal and an enable. **How socket 2 is set today is not read:** `tic.db` does not
  ask it (`?S914 4` would), and the rack IOC holds the line. Not read either: the TIC's
  instruction manual, for where this is at the panel.
- **The valve box answers with its identity,** so it runs the firmware of this branch
  (protocol 2), which acknowledges sets. Nothing was set by me.
- **Not connected, by what the IOC sees:** the interlock Opta and the flow meters.

### 2026-11-25: the owner changes where the gauges go (for the plan: the development session's)

Owner: "slight change of plans: inficon foes on the roughing line (because it has a smaller
flange than the others) and the APG and a regular AIM go on the 6-way. We defer the nAIM to
later. both APG and AIM should be controlled by the TIC station".

What it says, set against the plan of today (revision 0.33). **Nothing of it is connected or
seen yet; no file is changed by me.**

- **INFICON VGC401 on the roughing line:** as the plan has it (`gauge_foreline`,
  `PRESSURE:foreline:*`). New is only the reason, its smaller flange.
- **APG and a regular AIM on the six-way cross, both on the TIC.** Until now the plan has the
  APG and an AIM on the homemade gauge box (`gauge_ctrl`, `PRESSURE:apg:*`) and the nAIM beside
  the APG on the cross. The APG is on the TIC's socket 1 since today (`TIC:gauge1:*`); the AIM
  takes another socket (P70), and both read through `tic.db`, read only. An AIM is switched on
  by the TIC, at its panel or by a rule of the TIC's own; nothing in the IOC can switch it.
- **The nAIM is deferred:** `AIM:*` of the rack IOC stays without a device (INVALID).
- **The homemade gauge box is out of the system** (question 25 a). Asked "Is the homemade gauge
  box out of the system with this change?", the owner answered: "Yes, drop it". Its records
  (`PRESSURE:apg:*`, `PRESSURE:id` and the others of `gauge_ctrl`) have no device from now on.
- **Still open:** which socket the AIM goes on (question 25 b); it is not plugged in yet.
- **Touched by it in the plan and the GUI** (the development session's): the gauges' places and
  names (P70, P71), the drawing, the interlock rows that name "nAIM / gauge controller" and
  "APG gauge" as sources, and what the rack IOC loads for the gauge box and the nAIM.

### 2026-11-25: the rack IOC reads the TIC (A52, P65, P73)

Owner, after his pull and restart on the rack server: "ioc is restarted, check the TIC".

**Seen on hardware, from the lab computer at 15:06:09** (`caget -a` in the pvServer container;
`IOC-RACK:heartbeat` was 15):

| PV | Value | Alarm |
|---|---|---|
| `TIC:ident:get` | `TIC100;D39700640T;160070509` | none |
| `TIC:model:get`, `TIC:sw:get` | `TIC100`, `D39700640T` | none |
| `TIC:variant:get` | `TIC` | none |
| `TIC:gauge1:getpressure` | 750.062 | none |
| `TIC:gauge1:state:get`, `:units:get`, `:alert:get`, `:priority:get` | `On`, `PRESSURE (Pa)`, 0, `OK` | none |
| `TIC:gauge2:getpressure`, `TIC:gauge3:getpressure` | nan | LINK INVALID |
| `TIC:gauge2:state:get`, `TIC:gauge3:state:get` | `Gauge Not connected` | none |
| `TIC:turbo:state:get`, `:type:get`, `:speed:get`, `:alert:get` | `Stopped`, `EXT75DX Pump`, 0, 0 | none |
| `TIC:backing:state:get`, `:type:get`, `:alert:get` | `Off`, `Mains Backing Pump`, 0 | none |

- **The identity is valid** with the NUL byte in the controller's reply (`e4494e4`).
- **The by-path name of `69a08e7` is right:** the IOC reads the TIC through it. The link was not
  listed with `ls`; the port file's comment now says what was seen.
- **No single INVALID reading in five minutes** (P73): `camonitor` on `TIC:ident:get`,
  `TIC:variant:get`, `TIC:gauge1:getpressure`, `TIC:gauge1:state:get`, `TIC:turbo:state:get`,
  `TIC:turbo:speed:get` and `TIC:backing:state:get` from 15:06:23 to 15:11:23: one event each,
  the first value, and no alarm event. `IOC-RACK:heartbeat` gave 301 events in those 300 s.
  The station was idle then: pumps off, the gauge at its top value. Not watched: a running
  station, hours.
- `PRESSURE:foreline:getpressure` 763 without alarm throughout.
- The rule for `/dev/mist2/tic_station` (`b8506e0`) passes `udevadm verify` on the lab computer
  (udevadm 259: 1 file, 0 failed). It is not installed on the rack server.

### 2026-11-25: the TIC's adapter on the rack server, its socket name in the port file

Owner: "the TIC is on the rack server now, here is the output", from `mist-2@mist-2-rack-IOC`
(vendor and model ID, `ID_PATH` of every `/dev/ttyUSB*`):

| Device | USB ID | `ID_PATH` | What it is |
|---|---|---|---|
| `/dev/ttyUSB0` | `1192:1000` | `pci-0000:00:1d.0-usb-0:1.1:1.0` | Matsusada USB-OPT (`/dev/mist2/usb-opt` by the rule) |
| `/dev/ttyUSB1` | `1192:1000` | `pci-0000:00:1d.0-usb-0:1.2:1.0` | Matsusada CO-U32 (`/dev/mist2/co-u32` by the rule) |
| `/dev/ttyUSB2` | `0403:6001` | `pci-0000:01:00.0-usb-0:1:1.0` | an FTDI adapter; the VGC401's, I take it (the serial number is not in the paste) |
| `/dev/ttyUSB3` | `067b:2303` | `pci-0000:01:00.0-usb-0:4.4:1.0` | **the TIC's Prolific adapter, behind the extension's hub** |

- **Changed by me, one line** (as the port file's own comment and `CLAUDE.md` have it): the
  `TIC` line of `EPICS/ioc/iocBoot/iocRack/ports.real.cmd` opens
  `/dev/serial/by-path/pci-0000:01:00.0-usb-0:4.4:1.0-port0` in place of
  `/dev/mist2/tic_station`, until a rule by socket gives that name.
- **Not seen:** the link itself (its name is made from the `ID_PATH` as on the lab computer,
  where `...usb-0:9:1.0` gave `...usb-0:9:1.0-port0`), and the IOC on the TIC. Both show after
  the owner's pull and IOC restart on the rack server.
- **For the rule** (the development session's): `SUBSYSTEM=="tty"`, `067b`, `2303`,
  `ENV{ID_PATH}=="pci-0000:01:00.0-usb-0:4.4:1.0"`, in the form of the Matsusada lines.

### 2026-11-25: the TIC's line through a USB extension, a load test; the restarted rack IOC

**The extension.** Owner: "I have a USB extension cord that I put in between the PC and the TIC
now, I would like you to "stress-test" it. Poll it for five to 10 minutes and let me know what
the package loss is". Seen on the lab computer: the extension is a USB 2.0 hub (USB ID
`1a40:0101`, 4 ports) and the Prolific adapter hangs on its port 4. **The adapter's name by
socket changed with it,** from `pci-0000:00:14.0-usb-0:9:1.0` to
`pci-0000:00:14.0-usb-0:9.4:1.0`: a rule by socket on the rack server must be taken with the
extension in place, and the adapter must stay on that port of it.

**The test, seen on hardware** (14:06:24 to 14:16:24, the probe's ten queries one after the
other without a pause, each checked with the probe's own `meaning`, timeout 0.5 s; queries
only; the TIC on, both pumps off, gauge 1 at 1.0000e+05 Pa):

- **16210 queries sent, 27.0 a second; 16210 answered, all to the right object and in the
  form the protocol file expects. None lost, none wrong.** Per minute 1618 to 1627, all good.
- **Reply times:** min 23 ms, median 42 ms, mean 36.9 ms, 99 % below 63 ms, max 107 ms; one
  reply over 100 ms, none over 150 ms (the IOC's reply timeout since `e4494e4`). Without the
  extension, this morning: 20 replies of the probe, 23 to 86 ms, median 37 ms.
- **The kernel's log** has no line about USB, the hub or the adapter between 14:06 and 14:17:
  no reset, no reconnect.
- **Not seen:** what USB itself repeated. A damaged USB packet is sent again below what a
  program sees, and the adapter's driver (`pl2303`) gave no error counters. The test ran on
  the lab computer with the pumps off: not on the rack server's socket, not beside running
  pumps or high voltage, and for ten minutes only. The IOC asks about 6.5 times a second, a
  quarter of this load.

**The rack IOC after the owner's pull and restart** ("ioc is restarted after pulling, but I
didn't move the TIC over yet"), seen from the lab computer:

- 14:01:59: `IOC-RACK:heartbeat` 32. `PRESSURE:foreline:getpressure` 763 without alarm, state
  "Measurement data okay", `PCG`, `Torr`, "No error", `302-519-D`.
- **The pressure has a new time stamp every second** (the request's priority, `7ae5af5`): read
  every 0.4 s for 64 s from 14:02:32, 65 distinct stamps, gaps 0.82 to 1.22 s, median 1.10 s,
  none over 1.5 s. In the first seconds after the start (heartbeat 32 to 36) two stamps were
  2 s apart.
- `TIC:ident:get` COMM INVALID, `TIC:model:get` UDF INVALID, `TIC:variant:get` and
  `TIC:gauge1:getpressure` LINK INVALID: the TIC's adapter is still on the lab computer.

### 2026-11-25: a line from the rack server; the TIC's adapter is not there yet

The owner pasted, from `mist-2@mist-2-rack-IOC`, the output of
`udevadm info -q property -n /dev/ttyUSB1 | grep -E "ID_PATH=|ID_VENDOR_ID|ID_MODEL_ID"`:
`ID_MODEL_ID=1000`, `ID_VENDOR_ID=1192`, `ID_PATH=pci-0000:00:1d.0-usb-0:1.2:1.0`.

- **That is the Matsusada CO-U32 adapter, not the TIC's:** USB ID `1192:1000` in socket 1.2 is
  the line of `99-mist2-matsusada.rules` that gives `/dev/mist2/co-u32`. So on the rack server
  `/dev/ttyUSB1` is the CO-U32 today, which agrees with the rule (seen in the owner's paste).
  The number in my example command was a guess of mine.
- **The TIC's adapter** (Prolific, `067b:2303`) was still in the lab computer at 14:00 (`lsusb`
  there). Its line from the rack server is still to come.
- The rack server's host name and user are in `CLAUDE.md` now.

### 2026-11-25: the TIC station shut down over the serial line, by hand (owner's word)

Owner: "yes, push your commits and shut the TIC station down gracefully. I think tic_station is
a good name. ad 3. will do, ad 4. yes ok." **Two commands were sent by hand, on that word; the
repository's TIC files stay read only.**

- **The order** is the EXT75DX manual's (B722-40-880 Issue E, 4.8): the stop command, the
  backing pump off immediately after it, then venting. Venting was left to the station: the
  TIC is set to open its vent valve at 50 % speed (`?S922` answered 1).
- **Sent** at 13:37:31, in one gap of the log, with the replies and their times:
  `?V904` `=V904 4;0;0` 24 ms; `?V910` `=V910 4;0;0` 25 ms; `?V922` `=V922 4;0;0` 26 ms;
  **`!C904 0` `*C904 0` 19 ms**; `?V904` `=V904 4;0;0` 51 ms (still "Running");
  **`!C910 0` `*C910 0` 19 ms**; `?V910` `=V910 0;0;0` 25 ms (off at once, no state 2 or 3
  seen); `?V922` `=V922 4;0;0` 23 ms; `?V905` `=V905 100.0;0;0` 29 ms.
- **The run-down in the log** (the probe every 5 s; turbopump state, speed in %, gauge 1 in Pa):
  13:37:31 4, 100.0, 1.0000e-02 | 13:37:36 7, 92.5, 2.20e3 | 13:37:41 7, 73.2, 4.24e3 |
  13:37:46 7, 57.1, 9.38e3 | 13:37:50 7, 35.9, 2.51e4 | 13:37:55 7, 17.6, 5.35e4 |
  13:38:00 7, 9.4, 1.0000e+05 | 13:38:30 7, 1.6 | 13:39:11 7, 0.3 | 13:39:16 0, 0.1 |
  13:39:20 0, 0.0. **State 7 "Braking" from the first sample after the stop to 0.3 %, then
  state 0 "Stopped", 105 s after the command.** States 2, 3 and 6 were not seen. Gauge 1 in
  state 11 with alert 0 throughout; exactly 1.0000e+05 Pa from 13:38:00 on (the value it was
  adjusted to at atmosphere).
- **The TIC's vent valve output** (`?V922`, asked every 5 s): 4 up to 13:37:46 (speed 54.3 %),
  0 from 13:37:51 (speed 32.5 %): it changes at 50 %, as set.
- **Air came in before that.** Gauge 1 read 2.2e3 Pa (16.5 torr) 5 s after the stop, with the
  pump at 92.5 %, and about doubled every 5 s (4.2e3, 9.4e3, 2.5e4, 5.4e4 Pa) while the TIC's
  vent output still read 4. Where it came in I cannot see from the serial line. Two
  possibilities: the turbopump's own controlled venting from 100 % to 50 % (its manual's
  Table 18, if the vent valve hangs on the pump's electronics), or air back through the
  backing pump that I had just switched off. The manual warns against a fast pressure rise at
  full speed in a small volume. **If it was the backing pump, the stop order of the pump's
  manual is wrong for this cart, and the backing pump should stay on until the turbopump has
  stopped.** The TIC's own "system off" setup points the same way: it stops the turbopump and
  leaves the backing pump on (`?S933`: `904;0;1;910;1;0`). To settle at the cart: where the
  vent valve's cable goes, and whether the backing pump has an inlet valve.
- **Settled afterwards: it was the turbopump's own controlled venting.** Owner, asked where the
  vent valve's cable goes: "To the turbopump". Read through the TIC at 13:43:33 (a query,
  routed to the pump as D397-30-880 Table 1 says for objects from 800): `?S853` answered
  `=S853 1` after 112 ms. By the EXT75DX manual (Table 18 and the serial table) option 1 is
  controlled venting between 100 % and 50 % speed and the valve fully open below 50 %; the
  factory setting would be 0. That is what gauge 1 showed, so the stop order of the pump's
  manual fits this cart. `?V904`, `?V910` and `?V922` answered `0;0;0` then. `?S851` (pump
  type) came back as an empty line after 1 ms; not followed up.
  **Not explained:** the same manual says the pump's electronics shut the vent valve only at a
  start command, yet the backing pump alone reached 0.08 torr before the turbopump was started.
- **The log:** 355 runs of the probe between 13:10:12 and 13:40:06, ten of ten queries answered
  in every one. It is stopped; nothing holds the port.

**"tic_station"** (owner, above): I read it as the name he wants for the station's serial line
on the rack server (`/dev/mist2/tic_station`; the port file has `/dev/mist2/tic` today). The
adapter has no serial number, so the name needs a rule by the rack server's socket; its
`by-path` line is still to come from there.

**The GUI's Makefile on Compose 2.40.3** (commit `3c58422`, with the owner's OK): with the stack
up, `make -C RAS/mist2 dev-up` ended with exit code 0 in 4 s: the four images from the cache,
"check-ports: the mist2ras stack is already running, ports not checked", then **`pvserver` and
`frontend` were recreated** (new container IDs; `nginx` kept running), "MIST-2 GUI is up". The
page answered 200 afterwards. `make -n -C RAS/mist2 dev-down dev-logs` prints both commands
with `--profile build` (exit code 0); neither was run.

**Pushed** on the owner's word: `348f8a6` at 13:36, the lab session's first push.

### 2026-11-25: the TIC's turbopump started over the serial line, by hand (owner's word)

Owner: "start the turbo when the pressure is low enough". **One command was sent by hand, on
that word; the repository's TIC files stay read only.**

- **What "low enough" rested on:** the EXT75DX's manual B722-40-880 Issue E, Table 5: critical
  backing pressure 8 mbar for nitrogen, maximum continuous backing pressure 2 mbar with natural
  convection cooling (5 mbar with forced air); section 4.3: the pump may be started together
  with its backing pump. The TIC itself holds no condition: `?S904 4` answered
  `=S904 4;0;59;0.0000e+00;0.0000e+00;0` (no master gauge, not enabled) and `?S904 21`
  `=S904 21;0` (start delay 0). Gauge 1 read 1.04e1 Pa (0.104 mbar, 0.078 torr) and the backing
  pump had been on for 7 minutes.
- **Seen before the start** (13:27:17, queries only): air cooler `=V924 0;0;0` with `=S924 1`
  (slaved to the turbopump), vent valve `=V922 4;0;0`, turbopump `=V904 0;0;0`, backing pump
  `=V910 4;0;0`, `?S905` `=S905 8;8`, `?S910 70` `=S910 70;0`, `?V907`, `?V908` `0;0;0`,
  `?V906` `0.0;0;0`. With the vent valve in state 4 the volume held 0.08 torr: state 4 is the
  closed valve on this station.
- **Sent** at 13:27:28: `!C904 1` and CR (D397-30-880 Table 1, object 904, `!C`, "On =1, Off
  =0"). **Reply `*C904 0` after 19 ms.** `?V904` 32 ms later still answered `=V904 0;0;0`.
- **The run-up in the log** (the probe every 5 s; turbopump state, speed in %):
  13:27:27 0, 0.0; 13:27:32 5, 5.5; 13:27:37 5, 13.3; 13:27:42 5, 20.3; 13:27:52 5, 31.5;
  13:28:02 5, 41.8; 13:28:12 5, 50.1; 13:28:17 4, 54.3; 13:28:27 4, 62.3; 13:28:55 4, 82.5;
  13:29:06 4, 89.0. **State 5 "Accelerating" up to 50 % and state 4 "Running" from 54 % on;
  state 1 "Starting Delay" was not seen** (the delay is 0). The backing pump stayed in state 4.
  The log has a gap from 13:28:27 to 13:28:55, where I restarted it.
- **Gauge 1 during it:** 1.03e1 Pa at 13:27:27, 4.53e0 Pa at 13:27:32, 6.20e-1 Pa (4.7e-3 torr)
  at 13:27:37, and **exactly 1.0000e-02 Pa from 13:27:42 on, in state 11 with alert 0.** That
  is 1e-4 mbar, below the range of an APG100-XM (to 1e-3 mbar by Edwards' range table): the
  gauge's floor, reported as a valid reading. The IOC would show 7.5e-5 torr without an alarm.
  The owner's aim, 1e-3 torr, was passed within 15 s of the start.

### 2026-11-25: the TIC's backing pump switched on over the serial line, by hand (owner's word)

Owner, at the station, with the pump flange blanked off and the APG on the pumping port: "can
you start the roughing pump?". **One command was sent by hand, on that word. Nothing in the
repository sends a command: the probe, `tic.proto` and `tic.db` stay read only.**

- **Sent** at 13:20:03 on the lab computer, between two runs of the log: `!C910 1` and CR.
  Source: D397-30-880 Issue H, Table 1, object 910 "Backing Pump", operation `!C`, "Turn pump
  on/off", and the command list 1.7.5 (Device Off 0, Device On 1). The program that sent it is
  not in the repository; it can send `!C910 1` or `!C910 0` and nothing else, and uses the
  probe's own `open_line` and `ask`.
- **Seen on hardware:** the reply `*C910 0` after 19 ms (code 0, "no error", Table 3). `?V910`
  32 ms later: `=V910 4;0;0`, state 4 "On State". No state 1 "Off Going On" was caught.
- **In the log** (the probe every 5 s): backing pump state 0 up to 13:20:02 and 4 from 13:20:07;
  gauge 1 in state 11 throughout, 1.0000e+05 Pa before, 5.43e4 Pa at 13:20:07, 3.18e4 Pa at
  13:20:12, 2.87e4 Pa (215 torr) at 13:20:32. The turbopump stayed in state 0, speed 0.0 %: the
  command started the backing pump only.
- **The pump-down stalled, and why** (seen in the log; the cause is the owner's finding): from
  13:20:12 to 13:24:32 gauge 1 jumped between about 1.9e4 and 3.4e4 Pa (140 to 255 torr) and
  did not fall. Owner: "it was backed up, the exhaust was blanked off". With the exhaust open
  the value went from 2.51e4 Pa at 13:24:32 to 7.24e2 Pa at 13:24:47, 3.36e1 Pa at 13:25:02 and
  2.02e1 Pa (0.15 torr) at 13:25:32, still falling. State 11 in every sample; 185 runs of the
  probe by then, all ten queries answered in each. My own guess while it stalled, an open vent
  valve or a leak, was wrong.
- **Queries by hand while it stalled** (13:22:07, queries only, from D397-30-880 Table 1; not
  among the probe's ten): `?V922` (external vent valve) `=V922 4;0;0`; `?S922` (vent option)
  `=S922 1`, "On 50%"; `?V933` (system) `=V933 0;0;0`, off; `?S933` (system on/off setup)
  `=S933 904;0;1;910;1;0;913;0;0;914;0;0;915;0;0;916;0;0;917;0;0;918;0;0;0;0;0;0;0;0;0;0;0;0;0;0`,
  after 138 ms, the longest reply seen; `?V916`, `?V917`, `?V918` (relays) each `0;0;0`. The
  others took 23 to 32 ms. Whether state 4 of the vent valve means closed or venting I cannot
  tell from the manual.
- **Before that, the gauge:** the owner selected the new gauge at the front panel ("It said new
  id, when I selected it, it began reading"): state 2 with alert 9 until 13:12:27, state 11
  with alert 0 from 13:12:32, 4.62e4 Pa at atmosphere. Then his atmosphere adjustment ("I
  clicked the calibrate button and now it shows 1000, so it must be mbar"): 4.69e4 Pa at
  13:16:42, exactly 1.0000e+05 Pa from 13:16:47, state 11 in every sample. **So the display is
  in mbar and the serial value in pascal** (A52).

### 2026-11-25: the TIC, first contact (A52, P65, question 23)

**Seen on hardware: the TIC answers all ten queries at 9600 baud, 8N1, Xon/Xoff, in the form
the protocol file expects.** Probe `EPICS/ioc/host/edwards_tic_probe.py` of commit `9a6fe17`,
run twice on the lab computer (13:08:51 and 13:09:42), on the owner's word ("let's test it on
this computer"), no IOC on the port. Owner, at the second run: "the TIC station is powered up,
the USB-to-RS232 is connected, and I connected the APG gauge to the pumping port, so we can do a
full test down to 1e-3 Torr."

- **Variant (question 23 a):** `?V902` has 10 fields, the TIC Turbo and Instrument Controller.
  `?S902` answers `TIC100;D39700640T;160070509\x00;5.0`: the first field is `TIC100`, not `TIC`
  as in the manual's example, and **a NUL byte follows the serial number**, before the
  semicolon. `tic.proto` reads the whole identity with `%80[^\r]` and its first two fields with
  `%39[^;]`: what the NUL does to `TIC:ident:get` in the IOC is not tried.
- **Pumps (question 23 b):** turbopump type 3, "EXT75DX Pump", state 0 Stopped, speed 0.0 %;
  backing pump type 8, "Mains Backing Pump", state 0 Off. Both pumps were off at both runs.
- **Gauge sockets (question 23 c):** socket 1 answers `9.9000e+09;59;2;9;0`: no pressure
  reading, units type 59, state 2 "New Gauge Id", alert 9, priority 0. Sockets 2 and 3: state 0
  "Gauge Not connected". The owner's APG is on socket 1; the state was the same in both runs,
  51 s apart. **By A52 the IOC takes a value as a pressure only in state 11 "On":** in state 2
  `TIC:gauge1:getpressure` is INVALID. What ends the state "New Gauge Id" (a key at the front
  panel, or time) I have not read.
- **Reply times:** 23 to 86 ms; the identity is the slowest (61 and 86 ms), the gauges 42 to
  49 ms, the pump queries 23 to 32 ms. The IOC's `ReplyTimeout` is 120 ms.
- **Adapter (question 23 d):** Prolific PL2303, USB ID `067b:2303`, driver `pl2303`, **no
  serial number**, `/dev/ttyUSB0`,
  `/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0`,
  `/dev/serial/by-path/pci-0000:00:14.0-usb-0:9:1.0-port0` on the lab computer. Without a
  serial number it can be named by its socket only, on the rack server by that computer's
  `by-path` name. udev marks it `ID_MM_CANDIDATE=1`; ModemManager's log names it once at
  12:53:27 ("not supported by any plugin").
- **What the probe changed on the controller:** nothing; it sends the ten queries only.

**Not seen yet:** a gauge that measures (state 11, a pressure in pascal), a running pump, the
IOC on this controller, an error reply. A log of gauge 1 and of both pumps runs on the lab
computer during the owner's pump-down (the probe every 5 s, queries only).

The whole output of both runs:

```
run at 2026-11-25 13:08:51 +0100
?S902    identity            '=S902 TIC100;D39700640T;160070509\x00;5.0'    61 ms  type TIC100, software D39700640T, serial 160070509 , PIC software 5.0
?V902    system status       '=V902 0;0;2;0;0;0;0;0;0;0'           50 ms  10 fields: TIC (TIC Turbo & Instrument Controller)
?V913    gauge 1             '=V913 9.9000e+09;59;2;9;0'           42 ms  value 9.9000e+09 (no pressure reading), state 2 New Gauge Id, units 59 pressure, Pa, alert 9, priority 0
?V914    gauge 2             '=V914 9.9000e+09;59;0;0;0'           44 ms  value 9.9000e+09 (no pressure reading), state 0 Gauge Not connected, units 59 pressure, Pa, alert 0, priority 0
?V915    gauge 3             '=V915 9.9000e+09;59;0;0;0'           49 ms  value 9.9000e+09 (no pressure reading), state 0 Gauge Not connected, units 59 pressure, Pa, alert 0, priority 0
?V904    turbo pump state    '=V904 0;0;0'                         24 ms  state 0 Stopped, alert 0, priority 0
?S904 3  turbo pump type     '=S904 3;3'                           29 ms  pump type 3 EXT75DX Pump
?V905    turbo speed         '=V905 0.0;0;0'                       28 ms  speed 0.0 %, alert 0, priority 0
?V910    backing pump state  '=V910 0;0;0'                         24 ms  state 0 Off State, alert 0, priority 0
?S910 3  backing pump type   '=S910 3;8'                           23 ms  pump type 8 Mains Backing Pump
RESULT: 10 of 10 queries answered, 10 in the form the protocol file expects
exit code: 0
```

```
run at 2026-11-25 13:09:42 +0100
?S902    identity            '=S902 TIC100;D39700640T;160070509\x00;5.0'    86 ms  type TIC100, software D39700640T, serial 160070509 , PIC software 5.0
?V902    system status       '=V902 0;0;2;0;0;0;0;0;0;0'           43 ms  10 fields: TIC (TIC Turbo & Instrument Controller)
?V913    gauge 1             '=V913 9.9000e+09;59;2;9;0'           42 ms  value 9.9000e+09 (no pressure reading), state 2 New Gauge Id, units 59 pressure, Pa, alert 9, priority 0
?V914    gauge 2             '=V914 9.9000e+09;59;0;0;0'           42 ms  value 9.9000e+09 (no pressure reading), state 0 Gauge Not connected, units 59 pressure, Pa, alert 0, priority 0
?V915    gauge 3             '=V915 9.9000e+09;59;0;0;0'           42 ms  value 9.9000e+09 (no pressure reading), state 0 Gauge Not connected, units 59 pressure, Pa, alert 0, priority 0
?V904    turbo pump state    '=V904 0;0;0'                         32 ms  state 0 Stopped, alert 0, priority 0
?S904 3  turbo pump type     '=S904 3;3'                           23 ms  pump type 3 EXT75DX Pump
?V905    turbo speed         '=V905 0.0;0;0'                       27 ms  speed 0.0 %, alert 0, priority 0
?V910    backing pump state  '=V910 0;0;0'                         25 ms  state 0 Off State, alert 0, priority 0
?S910 3  backing pump type   '=S910 3;8'                           24 ms  pump type 8 Mains Backing Pump
RESULT: 10 of 10 queries answered, 10 in the form the protocol file expects
exit code: 0
```

### 2026-11-25: the station's controller is a TIC with three gauge sockets (question 23 a)

Owner: "It's front label says TIC and it has three RJ45 recepticals on the side". **This corrects
my entry below:** the station is not a T-Station with the simple controller. A TIC with gauge
sockets and a turbopump is the TIC Turbo and Instrument Controller or the Instrument
Controller; the probe's `?V902` line tells which (10 fields or 8). So T29 fits as far as the
owner's reading goes. Not yet told: whether its 9-pin "RS232/485" socket is there (Edwards'
data sheet shows it on the back), and what is plugged into the three sockets.

**The part number's family, read in Edwards' webshop on 2026-11-25** (a search for `TSM1D1002`;
the number itself is not listed, 19 neighbours are): the numbers of the "nEXT TIC Cart" have
this form, for example `TSK1D1002` and `TSJ1D1002` (nEXT85 TIC Cart, NW40), `TSK1D1001`,
`TSB4D1002` (nEXT240 TIC Cart, ISO100, listed with 100 to 115 V, one phase, 50/60 Hz) and
`TSC4D1002` (nEXT300 TIC Cart, listed with 110 to 115 V). So `TSM1D1002` reads as a TIC cart,
and its last digit agrees with the 115 V the owner read at the inlet. Not known: what the `M`
and the `D` stand for (which turbopump, which backing pump). A product page for the number
could not be read: the shop put a bot check in front of it, which I do not work around.

**Mains, unchanged: 115 V, not 230 V.** The TIC controller alone takes 90 to 264 V by its data
sheet, so the 115 V belongs to something else on the cart, most likely the backing pump. Its
rating plate and the cart's manual decide; neither is read.

**No probe has run.** The station has to be powered and its serial socket on an adapter first.

### 2026-11-25: the Edwards station is a 115 V unit, and may not be a TIC at all (A52, question 23)

Owner: "The station's part number is TSM1D1002 does it accept 230 V mains? Could the nAIM and
the Inficon and the Edwards APG100-XM in theory be driven through that controller?", and then:
"it says 115 V in tiny letters at the inlet receptacle".

**Nothing here is seen on hardware by me.** The label and the 115 V are the owner's reading; the
rest is read from Edwards' documents, fetched on 2026-11-25 (sources at the end).

- **Mains: not for 230 V.** The string `TSM1D1002` is in no Edwards list I found (two web
  searches for the exact string found nothing). Edwards' T-Station order numbers have its shape:
  `TS85D1002` is the T-Station 85H, dry (XDD1 diaphragm pump), NW40 inlet, 100 to 120 V, and
  `TS85D1001` the same for 200 to 230 V; `W` in place of `D` is the wet station (E2M1.5), and
  `TS85M1003` and `TS85M1006` are the dry station with an mXDS3s for 230 V and 115 V. A number
  that ends in `D1002` therefore reads as dry, NW40, 100 to 120 V, which agrees with the 115 V
  at the inlet. Not known: what the label's third and fourth characters really are (`85`, `75`).
- **A T-Station is not a TIC station.** Its data sheet and the range brochure give it a turbo
  and active gauge controller of its own, for one Edwards active gauge, and name no serial
  port. Three gauges and RS-232 are named for the stations that carry a TIC Turbo and
  Instrument Controller. The T-Station's instruction manual (D395-94-880) is not read: the
  copy found refused an automated download. **So whether T29 (`TIC:*`, `tic.proto`,
  `edwards_tic_probe.py`) fits the lab's station at all is open** until the owner says what
  the controller is: its front, the number of gauge sockets, a 9-pin serial socket or none.
- **The TIC Turbo and Instrument Controller itself**, if the station has one: mains 90 to 264 V
  a.c., 47 to 63 Hz; three active gauges on FCC68 (RJ45) sockets; Edwards' own active gauges
  are named and no other make: APG100, APGX-H, WRG, AIM, AIGX, ASG2 in the data sheet of 2020,
  and APG200, APGX-H, WRG200, AIM200, WRH, AIGX, ASG2 in that of 2024. A 200 W controller feeds
  a 24 V XDD1; other mains backing pumps are switched through a relay box. In the older EXPT
  station the backing pump decides the station's mains voltage (separate rows for 100,
  110 to 120 and 220 to 240 V).
- **The three gauges through the station's controller:**
  - APG100-XM: an Edwards active gauge, of the family the TIC's data sheet names. For a
    T-Station the lists name the APG100-XLC and the APG200-XLC, not the XM: its manual decides.
  - nAIM: a digital gauge (15 to 48 V d.c., RS-232 or RS-485, 9600 to 38400 baud, an
    open-collector set point). Its data sheet lists no analogue pressure output, and the
    brochure says a digital gauge needs no controller and is read by a PC or PLC directly. So
    not through the controller; it stays on its own serial line, as the IOC reads it now.
  - The INFICON head on the VGC401 (the controller reports `PCG`): Edwards names its own gauges
    only, and I found no statement that another make works. Taken as no. Pin assignments not
    compared.

Sources: Edwards data sheets "TIC Turbo and Instrument Controller" 3601 0650 01 (2020) and
3601 0654 01 (2024), "T-Station 85" 3601 0254 01 (2024), "nAIM Digital Active Inverted
Magnetron Vacuum Gauge" 3601 0398 01 (2018), the brochure "Turbomolecular Pumping Stations",
and the instruction manual "EXPT Pumping Station" B723-00-880 Issue B.

### 2026-11-25: the rack IOC reads the VGC401, and the GUI shows it (A51, P65)

Owner, after he had moved the adapter to the rack server and started the rack IOC: "I see the
pressure in the CS. The Turbo stays manual until I have more time."

**Seen on hardware, from the lab computer at 12:29** (`caget -a` in the pvServer container, over
Channel Access to 10.77.0.6):

- `IOC-RACK:heartbeat` counts (238, and 243 five seconds later).
- `PRESSURE:foreline:getpressure` 764 without alarm, with a new time stamp in each read;
  `:getstate` "Measurement data okay", `:getgauge` `PCG`, `:getunit` `Torr`, `:geterror`
  "No error", `:getversion` `302-519-D`. All without alarm.
- **So `vgc401.proto` reads the pressure reply with the blank after the comma,** and the
  timeout of 150 ms holds on the rack server. The probe's pattern and the simulator still do
  not know the blank.
- The TIC's PVs (`TIC:variant:get`, `TIC:gauge1:getpressure`, `TIC:turbo:state:get` and
  others) are LINK INVALID with "No valid reply": no TIC is connected.
- The IOC's time stamps and the lab computer's clock agree within about a second.

**Not seen by me:** the rack server itself. Whether the rule gave `/dev/mist2/vgc401` there,
which socket the adapter is in, and the IOC's log are the owner's to tell.

**The GUI against an IOC on another computer works** (`LAB-SETUP.md` section 6, "Not tried with
IOCs on another computer"): seen in a browser on the lab computer. The banner reads "MIXED —
Rack IOC on real hardware, HV platform IOC: mode unknown." and "Rack IOC: real" with a counting
heartbeat; the foreline gauge shows 7.64e+2 torr; the foreline valve shows "closed"; APG, nAIM,
interlock and TIC show INVALID; 13 fields of the platform say "no connection". The browser's
title is still "[SIM] MIST-2" with the rack IOC in real mode.

**The turbopump stays manual** (owner, above): nothing starts or stops it from the IOC for now.

### 2026-11-25: the GUI on the lab computer (`LAB-SETUP.md` section 6)

**The GUI runs on the lab computer and its page opens; no PV connects, because no IOC ran.**
Docker 29.1.3, Compose 2.40.3, buildx 0.30.1, all from Ubuntu 26.04.1's packages.

- **The build works:** `make -C RAS/mist2 dev-up` built all four images in 18 minutes (11:57:39
  to 12:15:31, 8 processors). Docker's images take 11.8 GB, its build cache 7.5 GB.
- **`make dev-up` then failed at its last step.** `docker compose -f compose.dev.yaml up -d
  --no-build` printed `service "pvserver" declares unknown service "epicsbase" as additional
  contexts epicsbase`, and make ended with exit code 2. This Compose refuses the project file
  whenever the profile `build` is off: `pvserver` and `frontend` name the services `epicsbase`
  and `node_cache` in `additional_contexts`, and those two are in that profile.
  `docker compose -f compose.dev.yaml config -q` fails the same way, and passes with
  `--profile build`. The Makefile's `dev-down` and `dev-logs` use the same command line
  without the profile; I have not run them.
- **Started by hand,** no tracked file changed:
  `docker compose -f compose.dev.yaml --profile build up -d --no-build pvserver frontend nginx`,
  then `tools/wait-for-gui.sh`: "MIST-2 GUI is up: http://localhost:3000/". With the profile
  and the three names nothing but the three services is started.
- **Seen:** the three containers run (restart policy `unless-stopped`, Docker starts at boot);
  pvServer's log shows `EPICS_CA_ADDR_LIST: 10.77.0.6`; the page opens in a browser on the lab
  computer with its eight tabs and no error in the browser's console.
- **No PV connects:** every field says "no connection". The rack server answers a ping, and its
  TCP port 5064 was closed at 12:16, so no IOC ran there; the platform computer is not online.
  The GUI with an IOC on another computer is therefore still not tried.
- **Seen on the page, for the development session:** with no IOC connected the browser's title
  is "[SIM] MIST-2" and the banner reads "EMULATOR — Rack IOC: mode unknown, HV platform IOC:
  mode unknown." The Overview lists "Foreline gauge" and "Edwards TIC station" beside the
  drawing (P66).
- **Settings:** `RAS/mist2/.env` (not under version control) has `EPICS_CA_ADDR_LIST=10.77.0.6`.
  The platform computer's address is to be added when it is online.

### 2026-11-25: the VGC401, first contact (A51, P65)

**Seen on hardware: the controller answers at 9600 baud, 8N1, no handshake, through a USB to
RS-232 adapter cable on the lab computer.** Probe `EPICS/ioc/host/inficon_vgc401_probe.py` of
commit `a9d84ee`, run twice, 19 s apart, no IOC, no other program on the port.

- **Adapter:** FTDI FT232R, USB ID `0403:6001`, serial number `FTE7S80M`, driver `ftdi_sio`,
  `/dev/ttyUSB0`, latency timer 16 ms (the driver's default, not changed).
  `/dev/serial/by-id/usb-FTDI_USB_Serial_Converter_FTE7S80M-if00-port0`, and
  `/dev/serial/by-path/pci-0000:00:14.0-usb-0:4:1.0-port0`, which is the lab computer's socket
  and of no use on the rack server. The adapter reports a serial number, so a rule by serial
  number could give `/dev/mist2/vgc401` on either computer. No rule is written.
- **Unit:** `UNI` answers `1`, Torr. **Gauge head:** `TID` answers `PCG`, Pirani/Capacitive.
  **Firmware:** `PNR` answers `302-519-D`; the manual tinb01e1-f is for `302-519-E`.
  **Error word:** `0000` in both runs.
- **Pressure:** `PR1` answers `0, 7.6400E+02`: status 0 (measurement data okay), 764 Torr. I
  did not compare it with the controller's display.
- **The pressure reply has a blank after the comma:** `'0, 7.6400E+02\r\n'`. The manual gives
  the form `x,sx.xxxxEsxx` (p. 60) and the example `0,8.3400E-03` (p. 75); the controller sends
  a blank where the sign of the value would be. Three places know the form without the blank:
  - The probe's pattern for `PR1` does not take it. It prints "NOT THE FORM OF THE MANUAL" and
    ends with "4 of 5" and exit code 1, although all five requests were answered in the second
    run.
  - `vgc401.proto` reads the reply with `in "%(\$1:_pr1:status)1d,%g";`. Whether `%g` takes the
    blank I have not tried: there is no EPICS on this computer.
  - The simulator sends `0,8.3400E-03`, without the blank (`test_inficon_vgc401.py`).
- **Reply times** (from the write of the request to the reply's line feed, on this adapter):
  18 replies, 17 of them between 91 and 112 ms, one after 20 ms (the acknowledgement of `PR1`
  in the second run). The IOC's `ReplyTimeout` is 150 ms: the longest reply seen leaves 38 ms.
  One exchange, acknowledgement and data, took 187 to 208 ms (132 ms for that `PR1`). The
  budget in `vgc401.proto` counts 6 exchanges in 2 s: about 1.2 s at these times.
- **The first request of the first run was refused:** `PR1` got `'\x15\x15\r\n'` (two NAK, then
  CR LF) after 100 ms, and nothing more within 1 s. Every later request was acknowledged, and
  `ERR` read `0000` right after it, although the manual (p. 58) says an error sets a flag in
  the error word. Not explained. One possible cause is characters that were already in the
  controller's input (next point).
- **The controller did not send by itself:** 3 s of listening, nothing, in both runs. For the
  first run this means that something had sent it a character before (manual p. 55), or that
  it does not send after power-on as the manual says. Not known which. ModemManager is active
  on the lab computer, and its log names the adapter at 11:02:06 ("couldn't check support for
  device ... usb1/1-4: not supported by any plugin"); whether it wrote to the port I cannot
  tell.
- **What the probe changed on the controller:** no setting. It read the error word once per
  run, which by the manual clears it.

**Not seen:** the IOC on this controller (the adapter hangs on the lab computer; for the rack
IOC it must move to the rack server, and the `VGC` line of `ports.real.cmd` still names
`/dev/mist2/vgc401`), a value in Micron (the controller is set to Torr), a reading under
vacuum, underrange and overrange, another baud rate, the controller's own sending.

Owner, 2026-11-25, after the probe: "the foreline pirani probe will go on the rack computer, it
was just attached here for testing". The adapter's name under `/dev/serial/by-id/` is made from
its serial number and not from the socket, so it should be the same on the rack server:
expected, not seen there.

The whole output of both runs:

```
run at 2026-11-25 11:56:31 +0100
INFICON VGC401 on /dev/ttyUSB0, 9600 baud, 8N1, no handshake
1. listening 3 s, sending nothing
   -> nothing arrived: the controller does not send by itself (it was asked before, or the line, the cable or the baud rate is wrong)
2. one request each; columns: request, meaning, part, raw reply, time, remark
   PR1  pressure and status         '\x15\x15\r\n'             100 ms  (not an acknowledgement, ignored)
   PR1  pressure and status    ack  ''                        1001 ms  NO REPLY
   UNI  pressure unit          ack  '\x06\r\n'                  91 ms
   UNI  pressure unit          data '1\r\n'                     96 ms  Torr
   TID  gauge identification   ack  '\x06\r\n'                 112 ms
   TID  gauge identification   data 'PCG\r\n'                   96 ms  Pirani/Capacitive
   ERR  error word             ack  '\x06\r\n'                  95 ms
   ERR  error word             data '0000\r\n'                  96 ms  no error
   PNR  firmware number        ack  '\x06\r\n'                  96 ms
   PNR  firmware number        data '302-519-D\r\n'            112 ms  firmware number and modification index
RESULT: 4 of 5 requests answered in the form of the manual
exit code: 1
```

```
run at 2026-11-25 11:56:50 +0100
INFICON VGC401 on /dev/ttyUSB0, 9600 baud, 8N1, no handshake
1. listening 3 s, sending nothing
   -> nothing arrived: the controller does not send by itself (it was asked before, or the line, the cable or the baud rate is wrong)
2. one request each; columns: request, meaning, part, raw reply, time, remark
   PR1  pressure and status    ack  '\x06\r\n'                  20 ms
   PR1  pressure and status    data '0, 7.6400E+02\r\n'        112 ms  NOT THE FORM OF THE MANUAL
   UNI  pressure unit          ack  '\x06\r\n'                 112 ms
   UNI  pressure unit          data '1\r\n'                     96 ms  Torr
   TID  gauge identification   ack  '\x06\r\n'                  96 ms
   TID  gauge identification   data 'PCG\r\n'                   96 ms  Pirani/Capacitive
   ERR  error word             ack  '\x06\r\n'                  95 ms
   ERR  error word             data '0000\r\n'                 112 ms  no error
   PNR  firmware number        ack  '\x06\r\n'                  95 ms
   PNR  firmware number        data '302-519-D\r\n'             96 ms  firmware number and modification index
RESULT: 4 of 5 requests answered in the form of the manual
exit code: 1
```

### 2026-11-25: the lab computer `mist-at-iba`

- **Seen:** Ubuntu 26.04.1, x86_64, 8 processors, 15 GiB of memory, 853 GiB free on `/`,
  Python 3.14.4. `eno1` has 10.77.0.1/24.
- **The serial port was closed to the user.** `mist` was in neither `dialout` nor `docker`, and
  the probe's first try ended with "Permission denied" and exit code 2, nothing sent. The owner
  added `mist` to both groups, which holds from the next login, and opened the port and the
  Docker socket for the running login (`setfacl -m u:mist:rw /dev/ttyUSB0 /run/docker.sock`),
  which holds until the adapter is replugged, Docker restarts or the computer reboots.
  `LAB-SETUP.md` names `dialout` for the two IOC computers (section 2) and not for the computer
  a probe runs on. Neither `sg` nor `newgrp` is installed, so a new group needs a new login.
- **Docker was not installed.** The owner installed `docker.io docker-buildx docker-compose-v2
  make` from Ubuntu's packages: Docker 29.1.3, Compose 2.40.3, buildx 0.30.1, GNU Make 4.4.1.
  `docker-buildx` is not in the list of `LAB-SETUP.md` section 6: on 26.04 `docker.io` only
  suggests it, and I asked for it because `compose.dev.yaml` builds with
  `additional_contexts: service:...`. Whether the build works without it is not tried.
- **Of `LAB-SETUP.md` section 1, point 4, on this computer:** `openssh-server` is installed,
  `tmux` is not, the sleep targets are not masked, ModemManager is active and enabled.
- **Addresses** (owner, 2026-11-25): "rack server is 10.77.0.6 and the platform computer is not
  online yet". Seen: 10.77.0.6 answers a ping from here in 0.26 ms, and its TCP port 5064 was
  closed at 11:59, so no IOC ran there then. The address is in `CLAUDE.md`.

25. **After the change of plan for the gauges (2026-11-25).**
    a. Is the homemade gauge box (`PRESSURE:apg:*`, `PRESSURE:diag_box:*`) out of the system
       now that the APG hangs on the TIC? **Answered: yes (answer 66).**
    b. On which socket of the TIC does the AIM go? **Answered: socket 2 (answer 66).**
    c. What should the six-way cross's two pressures be called? Today they have the names of
       the TIC's sockets (`TIC:gauge1:getpressure`). My proposal: keep those as the device's
       own names and add names by place in the lab's pattern as aliases, for the GUI, the
       logger and scripts (P71). Your word for the names.
    d. Should the vacuum interlock take its signal from the TIC (it has outputs of its own for
       set points), and if so which?

26. **For the start and stop of the TIC's pumps (2026-11-25).**
    a. Should the AIM be switched from the GUI as well, or by the TIC alone (your rule: not
       before the APG shows 1e-2 torr or lower)? **Answered the same day** (to the lab
       session): "Does the TIC switch it on automatically or would I go and do it from the
       panel? If the latter, definitely through the GUI too." So T32 gets a request for the
       gauge on socket 2, refused unless the APG is valid and at or below 1e-2 torr, and reads
       the TIC's own link for that socket, so that the GUI shows whether the TIC switches it by
       itself. Both are from the manual only: the gauge command was not tried on the
       controller. The IOC does not switch the AIM off by itself. Also yours: "The APG and the
       AIMs from the TIC cart should show as on the side flange", which is what T31 draws.
    b. T32 lets the IOC refuse a turbopump start while the backing pump is off, and a backing
       pump stop while the turbopump runs. Do you want a pressure condition as well (which
       gauge, which value) before the turbopump may start?
    c. Where does the cart sit in the system: does it back the big turbopump through the
       roughing line with the INFICON, or pump the six-way cross itself? The GUI's drawing
       needs that; until then its pumps are listed beside the drawing.
    d. Start and stop ask for confirmation in the GUI, as the vent valve does. Right?

## Not verified

- **The VGC401 has met its controller on 2026-11-25:** see "Seen on hardware, lab session". The
  rack IOC reads it since 12:29 of that day (764 Torr without alarm). The pressure reply has a
  blank that the probe and the simulator do not know.
- The INFICON VGC401 and the Edwards TIC on their controllers: the probes, the protocol files
  and the line settings come from the manuals (A51, A52, P65). The VGC401's manual was read
  from a third-party copy; of the TIC's variants only the Turbo Controller's instruction manual
  was read.
- The steps of `docs/emulation/README.md` on a fresh WSL2 installation: Docker was already
  installed on the machine used.
- Anything against real hardware, including `ports.real.cmd` and `run-ioc.sh ... real` on a real
  Linux computer, and autosave's directory `~/.local/state/mist2` there.
- The GUI in a browser on Windows by a person. It was checked with a headless browser inside
  WSL and by looking at screenshots. You opened it yourself on 2026-11-21, on a checkout that
  was in the middle of a merge.
- The check of the CO-U32 on the main lab computer (`LAB-SETUP.md` section 1): its Ubuntu
  version is not known to me, and the rule file's syntax was checked with the udev of 24.04
  only (older versions have no `udevadm verify`).
- An IOC inside `tmux` over SSH on the rack computer: not tried. That Ubuntu 24.04's USB serial
  drivers (`ftdi_sio`, `cdc-acm`, `ch341`, `cp210x`) are in `linux-modules-extra`, which
  `linux-image-generic` depends on, and that `ubuntu-server` depends on `tmux` and `usbutils`,
  is read from the packages (2026-11-24), not from an installed computer. Whether the server
  installer's shell has the driver was not checked.
- The dipole scan (T23 to T25): nothing on hardware. The backend for the real NI box beyond
  its message when no driver is installed; whether NI's driver for Linux serves the USB-6001
  at all (P56); the picoammeter's model and with it every command (A44); the real reply
  formats, line settings and times of the picoammeter; the 6487; Python 3.8 for the scan
  program and the service (run on 3.10 and 3.12); their installation on the lab computer;
  the three parts together.
- The firmware: two sketches compiled (valve box, interlock box), with Ubuntu's Arduino
  packages and not with the Arduino IDE; none flashed. That an Arduino Mega restarts when the
  IOC opens its port, and so releases all relays at every IOC start, is what I know of the
  board, not something seen here.
- T26: both rule files and every device name on hardware; that a Teensy, a Mega and an FTDI
  adapter report under Linux the serial string Windows showed; what the Faraday cup's two
  values are (`i1` is taken as the cup current in A in the plant model only); how a real
  protocol 1 board answers a malformed command (not modelled; the IOC sends `A` only).
- T27: the times for 100 points are computed, not measured; `readback_lost_after` is tested
  in the unit tests only; a DAQ service that hangs instead of closing its connection.
- The computers as installed: Ubuntu 26.04.1 only in containers of that release, not on the
  rack server or the lab computer; what ModemManager does with the Arduino ports there; the
  platform computer's distribution, compiler and Python (only 32-bit Ubuntu 16.04 and 18.04
  were tried, in containers on a 64-bit kernel); the loop service on the rack server talking
  to the platform IOC over the network.
- `LAB-SETUP.md` on hardware: none of its steps. What was run is its step 2 (clone and build)
  in containers of Ubuntu 20.04, 22.04 and 24.04 on the development PC, and a start of both
  IOCs there in `real` mode without any device. Not run: the udev rule and the probe with the
  adapters, any device name, the GUI against IOCs on another computer (in WSL2 it reaches them
  through Windows' address translation, by their addresses and not by broadcast), the loop
  service's installation, a build on the mini PC.
- The firmware sketches in `AVR/devices` and `AVR/Thermocouple`: not compiled or flashed by me.
  That a box with protocol 1 firmware still answers the array query `A` is read from
  `AVR/libcom1/README.md` and from the lab's protocol file of 2023, which uses the same query.
- The udev rule and the probe of `EPICS/ioc/host/` with the real adapter. The rule was checked
  for its syntax only: whether `ftdi_sio` takes the adapter and `/dev/mist2/co-u32` appears
  can only be seen with the adapter plugged in.
- The loop on the machine: every number of it comes from the plant model. The loop service
  on the platform computer (installation written, not tried), on Python 3.8 (run on 3.10 and
  3.12), and its systemd unit.
- A lost permit link for the AU supplies: their permit is in their own IOC, where a link
  cannot be lost. They carry the same records as the REK, which is tested.
- Tabs as windows and values set in place in a real browser by a person: checked in a headless
  browser. Whether a window really comes to the front is the browser's decision and cannot be
  seen there.
- The logger on a real computer and over days: the life times were tested with shortened
  times, the disk estimate is an extrapolation of 10 minutes, and of the Grafana dashboards I
  looked at one.
- The race that the second version of the request records excludes cannot be hit on purpose.
  What is tested is the structure (no record that defers its work) and a client that writes
  through an IOC restart (311 writes, none swallowed). The argument itself rests on the source
  of the base.
- The gap in the supplies' old first contact could not be hit on purpose either: the old
  records passed the new writer test. The test fails when the gap is widened to 0.3 s, and the
  structure test fails on the old records. The argument rests on the source of the base. The
  slow variant (ten restarts of the platform IOC) was not run.
- The race of P45 itself was never seen and cannot be hit on purpose. What is tested is the
  state it leaves (permit lost, request off, output on), reached by a direct write and by the
  front panel. P47 is read from the source only.
- The front panel in the tests is the simulator's: it answers queries under local control
  (A24, not known for the real supplies), and it keeps a SW setting made at the panel only
  while the test holds it. If the real supplies do not answer under local control, both
  readings are INVALID there and the rule does not act; nothing is worse than before.
- T21: that nothing is sent twice when the rule is evaluated between a completion and EPICS's
  own queued reprocessing is argued from the source; that moment cannot be hit on purpose.
  The window of P50 was not measured.
- P49, T22: nothing of it on hardware. The remedy assumes that the supplies of a chain answer
  in the order of the requests and that the STS reply carries the unit number as the manual
  prints it (A41). Replies out of order, or two replies colliding on a chain, are not covered.
  The cause of the stall of the machine that showed the fault is not known; it happened once.
- T22: the simulator holds its line while it delays a late reply, so the neighbour's own
  reply also comes late. A real chain may behave differently when one supply answers late
  (P52). What reads the AU monitors besides the GUI and the logger I took from the plan, not
  from a search of every client.
- T22: the engineer's last commit changed one test file only; I ran all four acceptance
  commands on that commit. After my own comment change in the protocol files only the plan
  check and the suite ran.
- With a line so held up that the read-back of the SW setting takes longer than a second, one
  more off sequence may go out after a normal permit loss. Read from the records, not tested.
- The ion gauge's read-back of its on/off state on the real serial port (A40).
- The Opta interlock firmware on an Opta: compiled and tested on a PC only (P61, P62).
- Grafana by a person in a browser: I looked at screenshots of one dashboard.
- The GUI over hours. The checks keep a window open for a minute at most. Each trend line
  keeps its last 3000 values, which is 5 minutes of a value that changes ten times a second.

## Subagents

- All subagents report the model ID `claude-opus-5-5`.
- 2026-11-24: T26 one round (2.4 h), T27 two rounds (1 h and 50 min).
- 2026-11-25: T28 one round (50 min).
- 2026-11-25: T29 (Edwards TIC) and T30 (INFICON VGC401) started side by side, each in its own worktree.
- 2026-11-25: T29 one round (64 min), T30 one round (45 min). Both reports named the model `claude-opus-5-5`.
- 2026-11-24: the engineer of T23 stopped once without a report (the harness: "no progress for
  600 s") near its end; resumed with a message, it finished in four minutes. Its work was
  committed up to that point.
- The Agent tool's own worktree isolation cuts worktrees from `master`, not from the current
  branch. The lead creates each worktree from `emulated-iocs` under `.claude/worktrees/<task>`
  (ignored by git) and names it in the brief (`briefs/`).
- A new worktree needs `git submodule update --init` before `make -C RAS/mist2 dev-up` (the
  RAS sources are a submodule).
- With three subagents and me on one emulation every acceptance run waits for the lock. A
  round of one task took two to four hours of wall time, most of it waiting.
- T19 needed one round: its brief named the fault with the source lines and the pattern that
  holds (T18 had needed two). The subagent worked 75 minutes, my verification took about as
  long, most of it the four acceptance runs one after the other.
- T20 needed two rounds, the second because of my brief (an input that made the rule depend
  on a scan period). The subagent worked two hours on the first round, most of it waiting for
  its own test runs, and a quarter of an hour on the second. One of its new tests depended
  on how fast its client reconnects and failed in my run; I changed it myself.
- T21 needed one round: the brief named the mechanism with the source lines I had read
  first, and asked for the fault to be made on purpose. The subagent worked 75 minutes.
- T22 needed one round. The subagent worked two and three quarter hours, most of it waiting
  for full runs of the device case, which takes 18 minutes now. It added a fault mode to the
  simulator, which the brief allowed, and said so. One of its own full runs had three
  failures that did not repeat (P53).
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
| The actuator is written by one record of the IOC (`LOOP-DIS:_write`), not by the service | One place enforces limits, slew and "only in PID", whatever the service sends |
| Anti-windup by conditional integration: the integral takes its step only as far as the output stays within its limits and only as far as the output really moves at the slew limit | No extra parameter, and the integral is never ahead of the output that was sent. A first version took no step at all at the slew limit and stalled |
| A permit of a loop or of a supply is read by a scanned record of its own, not directly by the calculation | EPICS does not process a record when its CP link disconnects, and a calc keeps its last value when an input fails. A scanned reader turns INVALID at its next scan |
| `EPICS_CA_CONN_TMO` of the platform IOC is 5 s, not the default 30 s | A rack computer that dies without closing its connections is noticed after about 8 s instead of about a minute. On the one fiber between two computers nothing speaks against it |
| The loop's permit conditions carry no alarm while they are simply not fulfilled | An off supply is a normal state everywhere else in the system. The reason of a hand-back says when a condition mattered |
| The logger was merged with five known defects, which are in a fix round | The two other follow-up tasks need its plan (a tier for every PV) and its records as their base. What I measured myself, that nothing is lost, holds. `emulated-iocs` is the integration branch and nothing is pushed |
| The logger is shown on the Infrastructure page only, with a chip in the status strip | It is infrastructure like the IOCs, and a dead logger must be seen from every page, also from a page in a window of its own |
| P25 is done now, not later | Values set in place put the request buttons on the Overview, where INVALID after every IOC start reads as a fault of half the machine |
| The roles drawn as trends are in the plan (section `trends`), not in the GUI's sources | The GUI and the Grafana dashboards each had a list, and they differed within a day (the loop's graphs) |
| A request record takes over its device's state with one check and three chained records, not with a `seq` | In EPICS 7.0.10 a `seq` runs every step as its own callback and releases the lock set between them (`seqRecord.c`, `processNextLink`). Chained records are processed inside the caller's lock, and a record in simulation mode finishes without its device support |
| The supplies' first contact has a database file of its own (`supply_first_contact.db`) beside `first_contact.db` | A supply's set point starts in simulation mode and a write before the take-over must lose, and the output take-over writes three records and stops the probe. The request records' file would have had to be bent for it. The structure is the same: one check, chained records, no `seq` |
| The interlock gate's rare case (P45) was reported and not changed in T19 | It is older than the task, it could not be shown with a test, and a remedy changes what the gate does. The brief said: change a `seq` outside the first contact only with a failing test |
| P45 is fixed by a rule on the state, not by repairing the one write that can be lost | A rule that holds for as long as the permit is lost does not depend on any single moment, and it covers a direct write and the front panel as well. The supplies get a hardware interlock (answer 27), so the rule is kept simple: one record, 1 to 2 s |
| `_permit:enforce` takes "on" from the SW setting or from the status, whichever is valid | The SW setting is read back after every switching, so the rule sees a lost off command within its two evaluations. The status is polled every second and also shows a switch-on at the front panel, which the SW setting would show only at its next read, up to 5 s later |
| It acts at two evaluations in a row, and not while a switching is under way | After a normal permit loss the readings still show "on" for some tens of milliseconds. Without the two evaluations the rule would send a second off sequence in some of them |
| No periodically read record among the inputs that make the rule wait | In the first version the read of the SW setting was one. With its period at 1 second the rule never acted (shown). A scan macro must not be able to switch the rule off |
| The rule also takes back a switch-on at the front panel while the permit is lost | The gate does the same at a permit loss (its off sequence begins with REN). With the permit present the front panel is not touched |
| The count of `_permit:enforce` is an internal record without alarm and is not logged | What it does shows in the logged records: the output state goes on and off again. If you want the count in the logger or on a page, it is one line in the plan |
| The operator's direction of the same race (P47) was reported and not changed | The owner ordered P45. The remedy for P47 is a different one (the gate's periodic evaluation through Channel Access) with a cost of its own, so it is his decision. He first left it (answer 28) and then ordered the fix (answer 29) |
| P47 is fixed at the switching record (`_out:resend`), not by evaluating the gate through Channel Access | The remedy I had named first rests on EPICS marking a busy record to run again. A second change within the start of a sequence takes that mark away, so a command could still be lost, and each gate would depend on Channel Access inside its IOC. The rule on the record's own state (value against value last sent) holds for any number of writes and needs neither |
| `_out:resend` sends what is in the record, also an on | The stored value is the gate's latest command. If the permit or the request changes meanwhile, the gate writes the new value into the same record, and that is what is sent |
| It is evaluated once a second | A lost command then goes out at most a second late, in a case that needs two commands within some tens of milliseconds. A faster scan would buy nothing an operator sees |
| T21 has no test in the system suite | The suite's time is used up (P32), and the lost write can only be made by a helper record, which belongs in the device case and not in an IOC |
| P49 was found in an acceptance run of T21 and is reported, not changed there | It is in the protocol files, older than both tasks, and its remedy needs a test of its own (one reply made late, two supplies at different voltages) |
| P49 is fixed in two parts, the second added by me: the line kept quiet after a mismatch, and a status check in front of every state or setting read | The first is what I had named to the owner. It puts the line in step but cannot stop the one reply that is read before the first mismatch, and at an IOC start that reply is the neighbour's output state, which the first contact copies into the request. Only the reply to STS carries the unit number, so that is the only check there is |
| The monitors are not checked | A status request in front of each monitor read halves the rate on a full line (measured 4.6 Hz instead of 9.2 with two supplies). What it would prevent is one value for one cycle after a reply more than 200 ms late. Left to the owner as question 16, with my recommendation to leave it. He left them (answer 31) |
| Only `emulated-iocs` was pushed, under its own name | The branch tracked `origin/libcom1-robustness-fixes`, so a plain push could have gone there. The task branches `emu/t*` are all merged and would be 21 more branches on the remote |
| On the real computers the IOCs are built on the computer (`build-epics.sh`), not run from the Docker image | `run-ioc.sh`, autosave's directory and the loop service's installation are written for it, serial devices and udev names need no pass-through, and the mini PC's system is not known well enough to count on Docker there. The script takes the release tags and the build steps of the image |
| The dipole scan is proposed as devices in the control system plus a Python program that is a Channel Access client, not as a script that talks to the hardware | You named both ways (answer 34). A script on the hardware would be a second master beside an IOC on the same device, and its magnet current and cup current would reach neither the logger nor the GUI. A scan is a sequence (set, wait, read, average, save), which is easier to read and change in Python than in records, and the loop service already works this way. It is what work package WP11 said |
| The dipole's devices are proven in device cases and loaded by no IOC yet | Where the NI box and the picoammeter sit in the new lab, and so which computer's IOC serves them, is not known. A third IOC in the emulation touches the suite, the GUI and the logger; that step waits for the facts |
| The NI box is served by a Python service that speaks libcom1 over TCP, not by a Python soft IOC as the plan first said | The IOC side is then the protocol file and the alarm rules that every libcom1 device already uses and that are tested; the service's replies are compared with the real library. The plan's note is brought up to date with T26's merge |
| The picoammeter is polled with `ABOR`, the queries, `INIT` | In its power-on state it measures continuously and executes no query until it is idle (manual 7-4). The brief forbade setting anything at an IOC start; these two commands stop and restart the measuring and set nothing. Price: the display updates once per poll, and a reading that takes longer than the poll period never completes (INVALID then, not an old value) |
| The scan program takes "what the device holds" from a PV of its own (`actuator.held`) | A set record is processed only when it is written, so it keeps its value when the device behind it has lost its state (as P10 says of the TDK). The service's held value is the truth; the scan compares the two at the start and ends when the held value is not known any more |
| A read-back INVALID for 5 s is "actuator lost", and so is every loss during the end move: exit 5, nothing written after | Waiting out a settle timeout and then writing an end move into a device that does not answer is the wrong order. 5 s is a free choice (ASSUMED in the definition) |
| The source supply has no alias under its old name | `AU-20P7-1` was this system's assumption and never a PV of the lab. The lab's name is `AU-20P15-1`, and your rule is that existing PVs keep their names |
| No identity records for the Faraday cup and the flow meters | Their boards speak libcom1 protocol 1, which has no identity; the records would be INVALID for ever. They are in the plan as proposed until the boards are flashed |
| The MFC's protocol file is not changed to the lab's | Ours reads everything the lab's reads, and more (a reply without a carriage return). Shown with a test, not committed |
| The plan's entries for T23 to T25 wait for T26's merge | T26 changes the plan in its branch; two regenerations of the plan's documents on two branches would only collide |
| StreamDevice 2.8.26 is compiled as C17 where the compiler would take C23 (GCC 15, Ubuntu 26.04) | It does not compile as C23, and the rule here is unmodified release tags. The flag goes on the make command line of that one module; base, asyn, autosave and the IOC build without it |
| If the platform computer's Python is older than 3.8, the loop service runs on the rack server | It is a Channel Access client only. The loop already depends on the link between the two computers (its permit `interlock_open` comes from the rack IOC), and the platform IOC holds the loop in MANUAL by itself when it does not hear the service (watchdog, 2 s) |
| The first installation uses the names under `/dev/serial/by-id/` in `ports.real.cmd` | They exist without any rule and stay the same across re-plugging. Only the Matsusada adapters need a rule, to get a serial port at all. Names under `/dev/mist2/` for the others can follow when the adapters are known |
| The wait after a mismatch is 50 ms | The reply still on its way arrives within 37 ms (9 request characters, 16 ms turnaround, 11 reply characters at 9600 baud). 50 ms is also the wait after a reply timeout. A mismatch for another reason (a set the supply did not execute) costs 50 ms of line time and nothing else |
| In a protocol with a command, the command goes out before the status check | A stray reply must never stop a switching or a set. The check stands between the command and its read-back, so a read-back cannot be confirmed by a neighbour's reply |
| T22's tests have two simulated lines of their own in the device case | Late replies on the lines of the other tests would disturb them. The price is five more supplies in the case's IOC and a run of 18 minutes instead of 10 |
| T22 has no test in the system suite | The suite's time is used up (P32). The same databases and protocol files run in the device case; I checked the rack configuration by hand in the full emulation |
| The logger stores what a loop writes to its actuator as a signal while the loop is in PID | Five writes a second are not set commands of an operator. The plan names the PV and the condition (`drives`), so a second loop needs no change in the logger |
| The Opta interlock keeps the old box's four channels, their order and USB serial (T28) | No PV, no database and no port changes. The IOC sees the difference only in the identity |
| Its interlock relays have no channel | Nothing received over the line may switch them. Tested with every command and with random lines |
| A door is reported closed only after its input has read closed for 1 s without interruption | The IOC reads the box ten times a second and latches the supplies off. A short opening or a bouncing switch must reach it |
| No latch in the Opta | As the old box's outputs. The IOC latches the supplies. Whether the hardware contact must latch is question 22 |
| The door decision runs in the loop that also communicates, with a watchdog of 8 s | As the old box, and simple enough to test on a PC. Its weakness is P62, to be tried on the bench before the contacts are used |
| Sketches are compiled in a container with fixed versions of the tools | A firmware build that can be repeated and checked here. Flashing stays with the Arduino IDE on the owner's computer |
| The foreline pressure is `PRESSURE:foreline:getpressure`, not the brief's `FORELINE:getpressure` (T30, at loading) | The plan had proposed that name since 2026-11-21 and it follows the lab's own pattern (`PRESSURE:apg:getpressure`). The database's prefix is a macro, so nothing in it changed; its default stays as the engineer tested it |
| Both new devices are read only, and the IOC still reads the VGC401's error word every 2 s although reading clears it (T30) | The manual says a persisting error is set again at once, so the word stays readable; a passing error shows for one reading. Not reading it would hide a controller error from the IOC |
| The plan's fault rule knows one more kind of record that needs a statement: a device record on an output link that is processed by its own scan or a forward link (T29, `plan/build.py`) | The TIC's query records are of type calcout: they send a query and read the reply, and the database does not say that a silent controller fails them. The same structure exists in the supplies' `current:limit`, stated as before (never INVALID by itself), so no existing device's entry in the registry changed (compared) |
| `vgc401.db`: the two links from the pressure reading to the state carry the severity (MS) (T30, by me) | The state was INVALID only through its state words, which the fault rule cannot see; with the links the registry predicts what the device case shows |
| The simulated TIC has a gauge on every socket, a turbopump and a backing pump (T29, at loading) | An empty socket is INVALID for good, and the system tests expect every PV valid while nothing is at fault. What the real station has is not known (question 23) |
| The start test of the VGC401's device case reads value and severity from one Channel Access reply (T30, by me) | It failed once in my run: a get that timed out during the IOC's restart was counted as a valid sample without a value |
| `vgc401.proto`: reply timeout 300 ms instead of 150 ms (by me, from the lab session's measurement) | Replies came after 91 to 112 ms; 150 ms left 38 ms. With 300 ms a silent controller still fits the 2 s cycle (6 x 300 ms); an acknowledgement without data does not (2.4 s), and then readings come late, not wrong |
| `vgc401.db`: the pressure request has priority HIGH in the port's queue (by me) | An exchange takes 0.2 s on the real controller. Queued behind the four requests of the 2 s scan the pressure record was still busy at its next scan and skipped it; with the priority it waits for one exchange at most |
| The simulated VGC401 sends the value with a blank for the sign and answers after 95 ms (by me) | As the lab's controller does (firmware 302-519-D). The device case and the emulation now run at the real controller's pace, which showed two tests that assumed a fast line |
| The VGC401's device case waits for each of the slower records, and its start test drops the channel from before the IOC's restart (by me) | With 0.2 s per exchange the gauge head and the firmware number are read after the pressure. A channel from before the restart found the new IOC only after seconds (seen: not connected for the whole 6 s of the test), a new one searches at once |
| The GUI's Makefile names the profile "build" and the three services in every Compose call (by me, from the lab session's report) | Ubuntu 26.04's Compose 2.40.3 refuses the project file otherwise, for up, down and logs. The base images are still built and never started |
| `tic.proto`: the identity ignores what follows its text (ExtraInput = Ignore) (by me, from the lab session's probe) | The lab's TIC puts a NUL byte after the serial number; the text conversion ends there and the rest counted as surplus input, so the record was INVALID. The PIC software version behind the NUL is given up |
| `tic.proto`: reply timeout 150 ms instead of 120 ms (by me, from the measurement) | Replies came after 23 to 86 ms. 150 ms leaves 64 ms on the slowest, and the 13 queries of a silent controller still take less than the 2 s cycle (1.95 s) |
| The TIC's three gauge sockets stay loaded although sockets 2 and 3 are empty (for now) | The owner asked about an AIM on the TIC, so a second gauge may come. Until then their PVs are INVALID with the state "Gauge Not connected" (P70) |

## Assumptions that need your confirmation

"Lab files" means the current databases, protocol files, both `st.cmd` and `dbl` output from
both IOCs, expected in the week of 2026-11-23. Settled by your answers and removed from this
table: A2, A3 (AU units and chains), A14 (valve channels), A18 (sensor box, old interlock box),
A19 (the output gate is wanted, and it latches).

| # | Assumption | Source | Settled by |
|---|---|---|---|
| A1 | The lab's PV names are those of the 2023 snapshot | `latest.zip`, lab GUI. Rack IOC settled by the lab's files of 2026-11-24 (answer 39): 57 names agree, three devices differ (T26). The platform IOC's names are still from the snapshot | The platform computer's files |
| A4 | AU20P15: 20 kV and 15 mA full scale, same 16-bit set and 12-bit monitor scaling as the P7.5 | Confirmed by the lab's `matsusada_au20p15.db` (answer 39). Its PV prefix is `AU-20P15`: T26 | Settled for the scaling |
| A5 | Negative supplies show positive numbers | 2023 database has no sign handling | You (D3) |
| A6 | Turnaround time of the Matsusada adapters: 5 ms in the simulator | Measured on hardware (answer 44): about 15 ms, the FTDI latency timer of 16 ms; a reply is complete 31 to 35 ms after its request. The emulation's numbers for 16 ms apply: about 6 monitor updates per second and supply with two supplies on a line. The timer can be set to 1 ms per adapter (a udev rule), which the emulation says gives about 9 | Decide after the test under remote control |
| A7 | REK150-24 on its own port, unit 1, 9600 baud | Repository `st.cmd` | Lab files |
| A8 | TDK at address 6, 19200 baud | `tdk.proto`, repository `st.cmd` | Lab files |
| A9 | Thermocouple board at 19200 baud | Firmware says 19200, both `st.cmd` say 9600 | Lab files |
| A10 | Gauge controller (Teensy) at 115200 baud. The real port file sets even parity as the lab's `st.cmd` did | Confirmed by the lab's `st.cmd` and notes of 2026-11-24 (Teensy even, Mega none) | Settled |
| A11 | MFC at address 254, 9600 baud. The snapshot's files are a draft: set point only, no flow read-back, commented out in `st.cmd` | `latest.zip` | Lab files |
| A12 | `MFC:getFlow` as the name of the flow read-back | My proposal in the lab's style | Lab files |
| A13 | The Faraday cup Opta's first value, `FC1:i1`, is the cup current in A; `FC1:i2` is not known | The names and the line are the lab's now (T26). The meaning is my assumption for the plant model only; the database claims no unit. The sketch was not found | You (question 18), the sketch |
| A47 | The flow meters give 1260 pulses per litre, so `FLOW:f<n>:getflow` is in l/min | The sketch's comment and factor (`reference/lab-2026`, `FlowMeters.ino`) | You (question 18), the flow meters' data sheet |
| A48 | The two door switches of the HV cage close when their door closes, so the Opta counts a high input as a closed door (T28) | The old sketch treats the interlock as closed when both inputs are high; how the switches were wired to the lost box is not recorded. Asked in question 21, not answered | One constant per input in the sketch. A switch that opens when the door closes would have to be read the other way round, and a broken wire would then read as a closed door |
| A49 | An input of the Opta reads its voltage against the supply's minus terminal (T28) | The data sheet gives the input's thresholds and names no reference terminal in words | Seen at the first bench check: an input at the supply's plus must read as a closed door. The supply is the +24 V rail of a NIM crate (answer 55), so the reference is that crate's 24 V return |
| A50 | The four solenoid valves are fed from the NIM crate's +24 V rail, the one that feeds the Optas | Answer 57 names the valves' power as a worry for that rail and does not say it in so many words | You |
| A51 | The VGC401 as the lab has it: 9600 baud (the factory default), a reply within 150 ms, a value in Micron stays in Micron above 99000 on the serial line, and its "RS232" socket takes a straight cable (T30) | The manual tinb01e1-f gives the default and the pins, no response time, and the change-over to Torr only for the display; read from a third-party copy of the manual, of which I checked four pages against the engineer's quotes | The probe `inficon_vgc401_probe.py` on the controller: reply times, unit, gauge head. **Seen on hardware, 2026-11-25 (lab session, "Seen on hardware"):** 9600 baud answers; replies after 91 to 112 ms, within the 150 ms; the cable is "a USB-to-RS232 adapter cable" (owner, answer 60), and what is between it and the "RS232" socket I have not seen. Not seen: a value in Micron (the controller is set to Torr). New: the pressure reply has a blank after the comma (`0, 7.6400E+02`), which the manual's example does not show |
| A52 | The TIC station: 9600 8N1 with Xon/Xoff and a straight cable (from the Turbo Controller's manual, taken to hold for the lab's variant), replies within 120 ms, a gauge that measures reports the state On and its value in pascal, and an object the controller does not have is answered with an error reply (T29) | The serial manual D397-30-880 covers all variants; the instruction manuals of the Instrument Controller and of the Turbo and Instrument Controller could not be fetched | The probe `edwards_tic_probe.py` on the controller: variant, states, reply times. **Seen on hardware, 2026-11-25 (lab session, "Seen on hardware"):** 9600 8N1 with Xon/Xoff answers, all ten queries in the form the protocol file expects, replies after 23 to 86 ms; it is the TIC Turbo and Instrument Controller (`TIC100`, 10 fields). Not seen yet: a gauge in the state On with a pressure, an error reply. New: a NUL byte after the serial number in the identity, and the gauge on socket 1 in the state 2 "New Gauge Id" with no reading |
| A15 | nAIM answers `!C752` as in the Edwards manual | INFICON's description of the protocol | The gauge |
| A16 | One Opta drives both NT 20, wired as "ON/OFF switch" (Fig. 6) | Manual | You, rear panels |
| A17 | NT 20 RS-232 record format is unknown. Simulator and parser use an invented format | Manual: "more details on request" | A capture from a unit |
| A20 | Emulation subnet `172.30.0.0/24` | Free choice | You, if it collides with a network of yours |
| A21 | Linux device names in `ports.real.cmd` are placeholders (`/dev/mist2/<name>`) | Only `/dev/mist2/co-u32` has a udev rule, not tested (`EPICS/ioc/host/`). The others do not exist yet | Work package WP4 |
| A22 | The platform IOC runs the same EPICS top as the rack IOC | Its `st.cmd` is unknown. Its operating system is a light Ubuntu variant (your answer 22), variant and version unknown, so the Python version there is unknown too | Lab files, and `lsb_release -a` on the mini PC |
| A23 | The defaults of the current limits are the full scales: 15, 7.5, 7.5, 7.5 mA and 24 A | No source for the real limits | You |
| A24 | A Matsusada supply in local control still answers queries (status, monitors) | Seen on hardware (answer 44): under local control it answers the status and both monitors, and not the settings `SW?`, `CH0?`, `CH1?`. The simulator answers all or none (`queries_without_remote`), so neither of its two ways is the supply's (P59) | The test under remote control, then the simulator |
| A25 | The turbopump is a TURBOVAC 1000 C with a DN 250 ISO-K inlet. Its hydrogen speed is estimated from the neighbouring model in the data sheet | Your "I think", Leybold GA 05.118/14.02 | The pump's type plate |
| A26 | The nAIM is calibrated for nitrogen | Your "I believe" | The gauge |
| A27 | My reading of your answer 10: the limit PV is `current:limit`, the lab's name stays as an alias, the defaults file is `limits.defaults` per IOC, and a change from the GUI is saved to a second file that overrides the defaults at the next start. The defaults file itself is not rewritten | Your answer, autosave's way of working | You |
| A28 | The turbopump reaches its speed in 60 s in the simulator. The data sheet says about 9 minutes | Free choice, so that a desk session does not wait | Say so if you want the real time |
| A29 | (Settled on hardware, answer 43: both adapters report `1192:1000` under Linux, the FTDI driver takes them, and neither reports a serial number over USB.) The CO-U32 in the rack is the adapter of your notes of about 2016: serial number `CO001144` (confirmed from its sticker, answer 37), USB ID `1192:1000` (three such devices in the Windows list, answer 38). The adapters report no serial number over USB as Windows saw them, so they are named by their USB socket | Your notes, and Matsusada's driver CD rev. 1.7.0 for the ID | `lsusb -v` with the adapter plugged in |
| A30 | Set point maximum of the discharge loop: 23 A | Free choice, below the 24 A full scale of the REK150-24 | You |
| A31 | Filament current under the loop: 80 to 90 A, at most 1 A/s | 90 A is your working point of 2026-11-21. 80 A and 1 A/s are free choices | You |
| A32 | Default gains Kp 0.5 A/A, Ki 0.35 A/A/s, Kd 0 | From the plant model (gain 3.56 A/A, time constant 1.45 s), not from MIST-2 | A step response on the machine, `LOOP.md` section 7 |
| A33 | Hand-back after 3 s of stale data, MANUAL after 2 s without the service, period 0.2 s | Free choices; the period from the model's time constant and the TDK line's load | You, the machine |
| A34 | Channel Access timeout of the platform IOC: 5 s | Free choice (default 30 s) | You, the network between the two computers |
| A35 | The loop service installs on the mini PC: Python 3.8 or later, pyepics 3.5.8, user `mist2`, `/opt/mist2` | Written for Ubuntu, not tried. Variant and version unknown (A22) | `lsb_release -a` on the mini PC, then the steps of `loops/README.md` |
| A36 | The logging tier of each PV group: measured values raw, supply power per second, cold-junction temperatures per minute, everything written and every state on change, heartbeats and internal records not at all | Proposal of the logger task, rules with reasons in the plan (section `logging`) | You, table in `LOGGER.md` section 1 |
| A37 | Disk for the logger: about 370 GB after two years, 1 TB with headroom | Measured on the emulation, where every analog value is noisy and changes in every second. Assumes the real ADCs are as noisy | You; the first weeks of real data |
| A38 | Logger settings: a time stamp more than 10 s from the logger's clock is replaced, an interval closes 2 s after its end, "not alive" after 5 s without a count, buffer alarms at 50 % and 90 %, 2 000 000 rows of buffer | Free choices of the logger task | You |
| A39 | Grafana lets everybody on the network read without a login, as the GUI does. Its port and the database's are open to the logger's own computer only unless a setting opens them | Free choice; you said "no login" for the GUI | You |
| A40 | The ion gauge's on/off state is bit 1 of the status word in its pressure replies, and a record that only listens (I/O Intr) receives the replies another record asked for | `aim.proto` (INFICON manual, A15), and the StreamDevice behaviour as seen in the emulation. Not tried on the real serial port | The real gauge: `AIM:enable` shows ON after an IOC start while the gauge is on |
| A41 | (The form is confirmed on hardware, answer 44: `#3 CF LO`. The order of replies on a chain is still assumed.) A Matsusada supply's reply to STS carries its unit number exactly as the CO manual prints it (`#<unit> CO RM`), and the supplies of a chain answer in the order of the requests | Since T22 every read of an output state or a setting checks that reply first; before, only the status read used it. If the real reply differs, no supply makes its first contact and the IOC log names the reply it got: the same input line in eight places of each of the two protocol files then | Hardware (`EPICS/ioc/host/matsusada_probe.py` prints the reply) |
| A42 | The rack server and the lab computer run Ubuntu 26.04.1, desktop installation (answer 41). The platform computer runs an older 32-bit Linux that can still install the build's packages and has a compiler the build accepts (GCC 5.4 of Ubuntu 16.04 was the oldest tried). Each reaches the internet during the build | The build script ran in containers of these three versions. Your answer 22 for the mini PC, answer 32 for the rack computer | `lsb_release -a` on both, and the first build there |
| A43 | Windows on the rack computer still lists the Matsusada adapters and the other serial adapters with COM number, USB ID and serial number although they are not plugged in | `Get-PnpDevice` lists devices that are not present (seen on the development PC, which has no serial adapter, so no COM port line was seen) | The command of `LAB-SETUP.md` section 1 on the rack computer, before the wipe |
| A46 | The picoammeter's line: 9600 baud, 8 data bits, no parity, 1 stop bit, CR as terminator both ways, no flow control | The 6485 manual names the choices (9-16, 9-17), not what is set. The reply formats are taken as the manual prints them | The instrument's COMM menu |
| A44 | The picoammeter of the dipole scan is a Keithley 6485 on its serial port | The plan says "Keithley, model tbc" on an "RS-485 to USB converter". The 6485 is my guess at the most likely model; T25 builds for it from its manual, with everything that depends on the model in the protocol file and the simulator | You: the type plate, or the instrument's answer to `*IDN?` |
| A45 | The magnet supplies are set and read through analog channels of one NI USB-6001 (plan: "analog 0-10 V"), and nothing else of them is remote | The plan's device list. Channels, volts per ampere, range, polarity, the number of supplies and whether NI's Linux driver serves the box are not known: configuration values in T24 | You (question 17), and NI's documentation, which T24 reads |

## Open points

Closed by your answers or by later work and removed from this table: P1, P2, P4, P8, P16, P17,
P18, P19, P20, P22, P25 (request records undefined after an IOC start: they take over the
device's state now, see "Done"), P40 (the supplies' first contact: one hold of the lock now, see
"Done"), P45 (the gate's off command that could be lost: the permit acts as a state now, see "Done"), P47 (an operator's off or on that could be lost: a stored switching command is sent when the record is free, see "Done"), P49 (replies of a Matsusada line out of step after one late reply: in step after one mismatch now, and state reads check the unit number, see "Done"), P41 (the MFC's set point of -20 % is wanted, answer 26), P35 (the REK output with the rack IOC stopped: fixed with the
loop, see "Done").

| # | Point | Needs |
|---|---|---|
| P3 | (Closed by T26: the flows come from the Opta in l/min, the sensor box is replaced. Kept for the record.) Unit of the sensor box water flows. The sketch's factor 0.06 fits litres per hour by one comment and not litres per minute by the other. The unit field is empty. The seven temperatures have no names in any source | Nothing, if the Opta replaces the box |
| P5 | The door PVs `INTLK:i1:get_interlock` and `i2` are binary records with the states Open and Closed. The lab's were analog records with the same numbers (1 = closed) | You, if a script depends on the type |
| P6 | The gauge controller keeps sending the last pressure after a gauge is switched off | Firmware, later |
| P7 | The nAIM instruction manual was not found. Its protocol is taken from INFICON's description of the "Edwards nAIM protocol" and from the Edwards TIC manual | You, with the gauge |
| P9 | `AIM:getpressure` is INVALID while the gauge is off or striking. It keeps the number the gauge sent | Tell me if you prefer another display |
| P10 | After a TDK power cycle the supply comes back with its output off, while `TDK:status:setpoint` still shows ON until it is written again. `TDK:status:get` shows the truth | GUI and loop design |
| P11 | MFC: the supplement does not show the reply to a set or a literal example of a negative reply. The protocol file accepts both forms of the positive reply | Lab files |
| P12 | Faraday cup: names, line and protocol are the lab's now (T26). Still not known: what its two values are, their unit, and its sketch | You (question 18), the firmware source |
| P13 | Turbopump Opta: its firmware does not exist. The channel map in `turbo.db` is its specification | Firmware, later |
| P14 | NT 20 monitor port: the record format is invented. `TURBO<n>:raw:get` and `:age:get` work with any one-line format | A capture from a unit |
| P15 | The simulator's `close` fault accepts and closes every reconnect, which makes an IOC with `@init` handlers log about 100 lines per second while the fault lasts. Better: stop listening | Later |
| P21 | Simulator core, wishes from the device tasks: several input terminators, line settings changeable at run time, transaction counts per command | Later |
| P23 | `make -C emulation plan` changes the tracked PDFs on every run, because Graphviz embeds the build time. PDFs that differ only by the time stamp are left as they are by hand | Later, if it annoys |
| P24 | A supply that does not answer gets the same share of the line as a healthy one, and each of its polls costs the reply timeout (200 ms). Its neighbour on the chain drops to 1.4 Hz until it answers again | Later, if wanted |
| P26 | The RAS pvServer was seen giving a long text (`TURBO<n>:raw:get` through `VAL$`) a time stamp that did not belong to that text. The GUI check tolerates it. Not investigated | Later |
| P27 | `status:read` of the AU and REK supplies is a multi-state record now. 0 OFF and 1 ON as before, 2 and 3 are new (local control). A client that reads the number sees no difference in remote mode | You, if a script depends on the type |
| P28 | A client that writes `<supply>:ToggleOutput` directly bypasses the remote command and the limit, and with the permit present nothing stops it. While the permit is lost such a switch-on lasts 1 to 2 s (`_permit:enforce`, T20). In the lab's database it bypassed the permit altogether. The operator's PV is `SetToggleOutput` | Access security, later |
| P29 | After an IOC start a supply ignores a switch request until 5 s after its first answer. A request written earlier is overwritten by the state the supply reports | Know it |
| P30 | The emulation's saved limit of the REK is 20 A, not the default 24 A. I did not write it, and no test writes that value | You |
| P31 | Seen once by the test subagent, not proven: a client that reads about 200 PVs every 0.1 s from the rack IOC made Matsusada monitors INVALID for a moment. Not at idle, and gone when the suite read less | Watch for it with the real GUI and archiver. The logger subscribes with monitors and never polls |
| P32 | The system suite takes 12.6 to 13.1 minutes: between 757 and 787 s in the runs of 2026-11-23 and -24 on the trees of T20, T21 and T22 (767 s on the merged head with T22), with a spread of 30 s between runs of the same tree. T20 added 3 s, T21 and T22 nothing. The budget I set for it is 13 minutes (780 s), and nothing enforces it. The Matsusada device case takes 17.7 minutes since T22 (10 before) | The margin is used up. The next test that restarts an IOC must come with a trim: the NT 20 and Matsusada fault tests are the slowest |
| P33 | A trend takes the time of a value from the IOC and the present from the browser's computer. With clocks that differ, the end of each line is drawn too long or not at all | Synchronised clocks (NTP) on the IOC computers and the operator's computer |
| P34 | The USB-OPT has no device name: its serial number is not known, and its USB ID is known only if Matsusada's current driver package (one ID, `1192:1000`) is its driver. No package names the USB-OPT | The PowerShell command in `EPICS/ioc/host/README.md` on the rack PC, or `lsusb` |
| P36 | With the loop's set point minimum at or above its maximum nothing clamps the set point (the output limits still hold). Documented in `LOOP.md`, not prevented | Later, two more records per loop |
| P37 | The logger needs its database when it starts (it registers its PVs there). After that a lost database is buffered | Later, if the two start in the wrong order on the real computer |
| P38 | The saved settings of the emulated IOCs are one Docker volume for every checkout. A set point changed by hand stays for the next user: my session of T16 left the loop's set point at 21 A, found and written back the same hour | The suite prints at its start what differs from the defaults. Write back by hand |
| P39 | The Grafana dashboards have their own small table of words for the trend titles, beside the GUI's | Later, with the role words in the plan |
| P42 | Once, during a logger test run with four users on the machine (2026-11-23 02:29:35), the TDK and the REK were INVALID for 86 ms at the same moment (reply timeouts). The logger recorded it correctly. Taken as a stall of the platform simulators under load, not proven | Watch for it, like P31 |
| P43 | The loop's limit flag is an event (kept for ever). At a steady set point it did not change in two minutes of PID; in the closed-loop test with steps and limits it changed 15 times in 2.5 minutes | Watch on the machine. A rule in the plan's section `logging` makes it a signal if it is too many |
| P44 | The GUI check failed twice for its engineer on connections that did not come within 20 s while three engineers loaded the machine, and once showed every PV in every window as not connected while Channel Access was fine. Not seen in my runs | Watch. The check now names the PVs that are not connected |
| P46 | After a start of the platform IOC the loop service writes its records again 4 to 13 s after the IOC answers (six measurements with the IOC stopped for 20 and 30 s, the same with and without T19): Channel Access finds a restarted IOC at its next search. Until then `LOOP-DIS:service:get` shows "not alive" and the loop stays in MANUAL. The GUI check reads all records 8 s after the start, so its note names the three records the service writes (`LOOP-DIS:_active`, `_count`, `_out`) in some runs and not in others | Know it |
| P48 | The device test `test_limit_survives_an_ioc_restart` (Matsusada case, older than T20) failed once in the engineer's runs of T20: not all PVs of AU-20P7-1 were valid within 20 s of an IOC restart. Which PV is not known, the log was overwritten. It passed in every other full run of the case, three of the engineer's and two of mine for T20, and the three full runs of T21. Its failure message names the PVs now | Watch it. If it fails again the message says where to look |
| P50 | Two things the rules of T20 and T21 leave as they are, both harmless. A value written into `ToggleOutput` in the first milliseconds of a switching, before its SW line is formatted, is sent by that switching itself and then once more by `_out:resend`: the supply gets the same setting twice. And when the gate's result changes in the microseconds in which the switching sequence is starting, and the gate's own scan sees it before the change event, the output still follows the latest result, but an on that overtakes an off sequence goes out without the current limit having been sent again just before; that matters only for a supply that has forgotten its limit. Read from the source (`seqRecord.c`, `StreamCore.cc`), the window not measured | Know it |
| P51 | After one reply that comes more than 200 ms late, a voltage or current monitor of a neighbour on the same line can accept one value of the same kind and show it without alarm until its next update: 0.15 to 0.20 s with two polled supplies, up to 0.54 s with three in my run (0.66 s in the engineer's). At most one value per late reply; `power:read` is computed from it. The raw number is scaled with the wrong supply's full scale. The state and setting reads cannot do this since T22. The rack's two lines carry two supplies each; the REK is alone on its line, so its monitors and the discharge loop are not affected | Know it. Your decision of 2026-11-24 (answer 31): the monitors stay as they are. Checking them too would close it and halve their rate |
| P52 | A supply whose every reply is late (300 ms, left on for 10 s in the device case) leaves its neighbour on the line almost without readings: nearly all of the neighbour's records INVALID, one monitor value of the late supply accepted, no state or setting of the other supply shown. In step within a quarter of a second when the fault is cleared (the engineer measured 2 s with the old files). Part of it is the simulator, which holds the line for the late reply. A supply or an adapter that is always slower than 150 ms would need a longer reply timeout in the protocol files | Know it. Measure the reply times on hardware (WP4) before the timeout is trusted |
| P53 | One full run of the Matsusada device case by the engineer of T22 had three failures that did not repeat in three later full runs, one of them mine: `AU-20P7-1:output:init` in alarm in the test that every PV is valid, and two supplies not valid again within 12 s and 20 s after a fault. Cause not shown. For the first there is a reading from the source: `output:init` writes `voltage:get.PROC` through a Channel Access link, a put through a link that is not connected yet returns an error (`dbCa.c`, `dbCaPutLinkCallback`), the seq goes on (`seqRecord.c`), and the record keeps a LINK alarm because it runs once per IOC start. The voltage echo is then read at its next 5-second scan, and the gate is enabled as usual. The case's IOC has five more supplies since T22, so its links connect later. The helper `not_valid` prints the alarm status now, so a second time will say more | Watch for it. If it shows again: start `output:init` only when its link is connected, or read the echo through a database link |
| P54 | A pause of a simulator process (or of the whole machine) longer than 150 ms makes every Matsusada line of that simulator miss one reply at the same moment. Seen twice: in a device-case run for T21 (all four lines; it showed P49), and in the first suite run on the merged head of T22 (both rack lines, 5 ms apart, one monitor of each INVALID for one cycle; `test_05_faults` then fails, because another device's PV was INVALID while a fault lasted). Cause not known; the host is a WSL2 machine. Since T22 such a pause costs one TIMEOUT per line and, if the reply comes later than 200 ms, one mismatch, and the line is in step again | Know it: a failed `test_05` that names monitors of AU supplies on both lines at once is this, and the suite passes when run again. If it gets frequent: let the simulator log a late wake-up, to see how long the pauses are |
| P58 | The logger's database and the IOCs' saved settings are one Docker volume each for every checkout. A branch with other PV names logs a failed restore once and fails its saved-settings check once; the logger keeps the PVs of earlier registries with their last rows. Seen in T26 | Know it. On the real system a renamed PV starts a new history; the old one stays readable under its old name |
| P59 | Under local control a real Matsusada supply answers the status and the monitors and not the settings (answer 44); under remote control it answers all of them (answer 45). While a supply is under local control, the IOC's reads of its settings (`read_output_status`, `voltage:get`, `current:get`) will time out: those records are INVALID, which is true, and each read costs its line 200 ms. The simulator cannot behave so yet, and the tests of the local-control cases (T20) ran with a simulator that answers everything | The test under remote control first. Then: the simulator as the supply is, the device case run again, and perhaps no setting reads while the status says "local" |
| P55 | In the libcom1 databases whose element records are processed by a forward link of the array record (`faradaycup.db`, `solenoidbox.db` and the others of that pattern), an element record may show the value of the previous poll: the engineer of T24 measured it on his own database (one poll, 0.5 s, late) and used CP links there. Not checked on the other databases, not changed. For the interlock box that would be 0.1 s on `interlock_open` | Check it on one of them (T26's Faraday cup case can show it). The hardware interlock is the first line |
| P56 | Whether NI's driver for Linux serves the USB-6001 is not shown: the NI-DAQmx for Linux readme 21.3 lists no USB-600x device, later readmes point to a compatibility page the engineer could not read, a knowledge-base article that says "not supported" could not be fetched. If it does not, the choices are in `DAQ.md` (a Windows computer for the service, NI hardware that is supported, a microcontroller with libcom1) | You: does LabVIEW drive the box on the Ubuntu lab computer today, and with which NI driver? |
| P57 | The scan program and the DAQ service use `max_step`, limits and a communication timeout whose values are all ASSUMED (`scans/config/dipole.yaml`, `daq/config/dipole.yaml`). A first scan on the machine needs your values in both files | Question 17 |
| P60 | That an IOC restart leaves the valve box's relays as they are (answer 52) is shown for the IOC's side only: the serial driver's hang-up flag on a pseudo-terminal, and the kernel's rule that DTR is dropped at close only with that flag on, read and not run. Not seen on the Arduino Mega. The interlock box is an Opta now (T28): it does not restart on DTR at all, only when its port is opened at 1200 baud | One test on the box: relay 5 on, restart the IOC, the relay stays on and `VALVE:s5:set` and `VALVE:s5:get` read 1. If it drops, the automatic reset has to be disabled on the board |
| P61 | The Opta sketch has never run on a board (T28). Not shown: that `digitalRead` of I1 and I2 reads those terminals (the core's two pin tables name different processor pins for the second input; the user manual's example reads it this way), that a high output closes a relay, what the relays do while the bootloader runs, whether the watchdog disturbs an upload, and that the box starts with 24 V alone, without USB | The bench checks in `LAB-SETUP.md` and in the sketch's README |
| P62 | In the Opta sketch the door decision and the communication share one loop, as in the old box. The Opta's USB write waits until the computer has taken the data (`USBCDC::send` in the core). If a write ever hangs (the USB cable pulled in the middle of a reply, a computer that stops with the port open), the doors are not read and relays 1 and 2 keep their state until the watchdog restarts the board, up to 8 s later. The IOC's side is safe in that state: no reply, `interlock_open` INVALID, supplies off. Whether a write can hang at all is not known | A bench test (`LAB-SETUP.md`): with the IOC reading, pull the USB cable, then open one input; relay 1 must drop at once. If it does not, the door decision moves into a thread of its own before the contacts are wired to anything |
| P63 | The Opta's relays have a minimum switching load of 300 mW (data sheet: 12.5 mA at 24 V, 60 mA at 5 V, 60 V at 5 mA). An interlock input of a power supply usually carries less; what the Matsusada and REK inputs carry is not known here | Question 22 b. A small signal relay between the Opta's contact and such an input |
| P64 | The unit test `test_matsusada_co ... test_back_to_back_transactions_keep_the_line_timing` failed twice on 2026-11-25 while other containers ran on the PC (0.02427 s and 0.02438 s against a limit of 0.02425 s) and passed alone. Its margin of 0.5 ms is too small for a loaded PC | Widen the margin or measure against the simulator's own clock. It is not a fault of the simulator's timing as far as these runs show |
| P65 | The VGC401 and the TIC are read by the rack IOC from their manuals only (A51, A52). If a real reply takes longer than the timeout (150 ms, 120 ms), its PVs are INVALID although the controller works | The two probes print every reply time; then the timeouts follow the measurement. **VGC401, seen on hardware, 2026-11-25 (lab session):** 17 of 18 replies after 91 to 112 ms, one after 20 ms, on an FTDI adapter with a latency timer of 16 ms; 38 ms are left of the 150 ms. **TIC, seen on hardware, 2026-11-25 (lab session):** 20 replies after 23 to 86 ms on a Prolific PL2303 adapter, against a timeout of 120 ms; the identity is the slowest |
| P66 | The two new devices are in the registry (class gauge) and in no drawing of the GUI | With the next GUI round: the foreline gauge beside the turbopump's foreline, the TIC where its gauges turn out to sit |
| P67 | ModemManager runs on the lab computer and looked at the VGC401's adapter before the probe ran (lab session, 2026-11-25). If it sent a character, the controller's own sending has ended, and the probe's listening shows nothing although cable and baud rate are right | The probe's requests still answer in that case. To see the automatic lines: the rule file installed (it keeps ModemManager off this adapter) or ModemManager disabled, then the controller switched off and on |
| P68 | With no IOC connected the GUI's title reads "[SIM] MIST-2" and its banner "EMULATOR — Rack IOC: mode unknown, HV platform IOC: mode unknown" (lab session, on the lab computer, 2026-11-25). On the real system that is wrong | GUI: the emulator's title and banner only when an IOC reports the mode of the emulation; an unknown mode as its own, neutral message |
| P69 | The real VGC401 refused the first request of the probe's first run with two NAK characters and answered every later one (lab session, 2026-11-25); the error word read 0000 right after. Characters already in the controller's input are a possible cause (ModemManager, P67) | The IOC asks again a second later, so it costs one INVALID reading. If it recurs with the rule file installed: send ETX first (the manual, p. 57: it clears the controller's input) |
| P70 | The lab's TIC has a gauge on socket 1 only, so `TIC:gauge2:*` and `TIC:gauge3:*` are INVALID for good on the real system and show so in the GUI | When it is clear whether an AIM or another gauge comes onto the TIC: load the gauge records per socket (one database per socket), or leave them |
| P71 | The TIC's pressures have the names of its sockets (`TIC:gauge1:getpressure`), not of the place they measure, unlike the lab's other pressures | Names or aliases in the lab's pattern once the gauges' places are fixed (the APG is on the cart's pumping port for now) |
| P72 | A gauge at the lower end of its range is a valid reading for the TIC and so for the IOC: the APG showed exactly 1.0000e-02 Pa (7.5e-5 torr) in the state On with the turbopump running (lab session, 2026-11-25). The VGC401 marks the same situation as "Underrange" | Your word whether such a value should carry a MINOR alarm. It needs the floor of each gauge type, which the IOC does not read from the TIC today |
| P73 | The TIC's reply timeout of 150 ms has 43 ms to spare on the slowest of 16210 replies (107 ms, through the owner's USB extension; lab session's load test, 2026-11-25). A reply that takes longer gives one INVALID reading. Not covered by the test: the rack server's socket, running pumps or high voltage nearby, more than ten minutes | Watch for single INVALID readings of `TIC:*` once the logger runs. A longer timeout needs the slower queries (identity, pump types) asked less often, or a silent controller no longer fits the 2 s cycle |

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
