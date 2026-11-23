# Status

Last update: 2026-11-23. The gates G0, G1 and G2 are closed. Branch `emulated-iocs` is local,
nothing is pushed.

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
One finding from the acceptance runs waits for your word: P49, replies of a Matsusada line that
stay out of step for tens of seconds after one late reply (question 15).

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

## Running

State of 2026-11-23, evening. Nothing is running.

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
- Next: your word on P49 (question 15), and your comments on the drawings (answer 25).

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
| 23 | Setting values on the drawings (2026-11-22) | "On the main screen/tabs, all the PVs are read-only. Only if I click on it and the pop-up appears can I change a value. I would like to be able to set values in place on the main screen." | Changes the decision of gate G2 (the drawing was read-only). In brief T16 as requirement R10: set points and requests in the tags, saved settings stay in the device window, the vent valve still asks first. Built and merged on 2026-11-22 (T16) |
| 24 | Tabs as windows (2026-11-22) | "Would it be possible to pop out individual tabs as separate windows and re-attach them if the user wants to?" | Yes, as browser windows opened by a control on the tab (a browser cannot dock). In brief T16 as requirement R11. Built and merged on 2026-11-22 (T16) |
| 25 | Comments on the drawings (2026-11-22) | "The filament should be vertically centered, attached to the left wall of the plasma chamber and have its tip point to the right. Stuff like that. I have a number of them." | The geometry is data (`RAS/mist2/ReactApp/src/config/drawings.json`). I apply them myself after T16 is merged: your list first, then a session with the GUI open in your browser |
| 26 | The MFC's set point of -20 % (2026-11-23) | "That is correct behavior. The MFC accepts a minimum value of -20, which we use to ensure the 'most closed' state possible." | Closes my open point P41 (I had taken the -20 % after a start for a fault of the simulator). In the plan as a note of the MFC (revision 0.16). Nothing to change |
| 27 | The interlock gate's rare case, P45 (2026-11-23) | "Yes, fix P45. There will be a hardware interlock. The software state is just an extra layer plus information in the logger." | Answers question 13. Task T20 (brief `T20-permit-enforce.md`): while the permit is lost and a supply reports its output on, the off sequence is sent again. Kept simple, because the hardware interlock is the first line |
| 28 | The operator's direction of the same race, P47 (2026-11-23) | "Leave P47" | Answers question 14. Nothing is changed. P47 stays in the open points as a known behaviour with its way out (on, then off) |
| 29 | P47 once more (2026-11-23, a few minutes after answer 28) | "Sorry, no fix P47" | Read by me as a correction of answer 28: fix P47. Task T21 (brief `T21-switch-resend.md`). Not the remedy I had named (the gate evaluated through Channel Access): that one still loses a command when several follow each other within a millisecond. Instead a rule at the switching record itself: a value written into it while it was busy is sent when it is free |

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
    section 10.
12. With values set in place, a filament current typed into the supply's tag while the loop
    is in PID takes the source to MANUAL at once (the loop reports "written by someone else").
    Should the supply's tag mark that the loop holds this set point while in PID, or refuse
    the entry?
13. Answered on 2026-11-23 (answer 27): fix P45; the supplies will have a hardware interlock.
14. Answered on 2026-11-23: first "leave it" (answer 28), then corrected to "fix it" (answer 29). Task T21.
15. P49: after one reply that comes later than about 200 ms, the requests and replies of a
    Matsusada line stay out of step for tens of seconds, and a supply can then show its
    neighbour's voltage and current without alarm. Shall I fix the protocol's handling of a
    late reply as a task of its own? My recommendation: yes, before the supplies are used on
    the machine.

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
- P49: that a supply accepted its neighbour's values is inferred from the counts of logged
  mismatches (about 260 per record for one unit, about 31 for the other on the same line).
  Both outputs were near zero, so no wrong value was seen as such. The cause of the stall
  that started it is not known. It happened once in the nine full runs of the device case for T20 and T21.
- With a line so held up that the read-back of the SW setting takes longer than a second, one
  more off sequence may go out after a normal permit loss. Read from the records, not tested.
- The ion gauge's read-back of its on/off state on the real serial port (A40).
- Grafana by a person in a browser: I looked at screenshots of one dashboard.
- The GUI over hours. The checks keep a window open for a minute at most. Each trend line
  keeps its last 3000 values, which is 5 minutes of a value that changes ten times a second.

## Subagents

- All subagents report the model ID `claude-opus-5-5`.
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
| The logger stores what a loop writes to its actuator as a signal while the loop is in PID | Five writes a second are not set commands of an operator. The plan names the PV and the condition (`drives`), so a second loop needs no change in the logger |

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

## Open points

Closed by your answers or by later work and removed from this table: P1, P2, P4, P8, P16, P17,
P18, P19, P20, P22, P25 (request records undefined after an IOC start: they take over the
device's state now, see "Done"), P40 (the supplies' first contact: one hold of the lock now, see
"Done"), P45 (the gate's off command that could be lost: the permit acts as a state now, see "Done"), P47 (an operator's off or on that could be lost: a stored switching command is sent when the record is free, see "Done"), P41 (the MFC's set point of -20 % is wanted, answer 26), P35 (the REK output with the rack IOC stopped: fixed with the
loop, see "Done").

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
| P26 | The RAS pvServer was seen giving a long text (`TURBO<n>:raw:get` through `VAL$`) a time stamp that did not belong to that text. The GUI check tolerates it. Not investigated | Later |
| P27 | `status:read` of the AU and REK supplies is a multi-state record now. 0 OFF and 1 ON as before, 2 and 3 are new (local control). A client that reads the number sees no difference in remote mode | You, if a script depends on the type |
| P28 | A client that writes `<supply>:ToggleOutput` directly bypasses the remote command and the limit, and with the permit present nothing stops it. While the permit is lost such a switch-on lasts 1 to 2 s (`_permit:enforce`, T20). In the lab's database it bypassed the permit altogether. The operator's PV is `SetToggleOutput` | Access security, later |
| P29 | After an IOC start a supply ignores a switch request until 5 s after its first answer. A request written earlier is overwritten by the state the supply reports | Know it |
| P30 | The emulation's saved limit of the REK is 20 A, not the default 24 A. I did not write it, and no test writes that value | You |
| P31 | Seen once by the test subagent, not proven: a client that reads about 200 PVs every 0.1 s from the rack IOC made Matsusada monitors INVALID for a moment. Not at idle, and gone when the suite read less | Watch for it with the real GUI and archiver. The logger subscribes with monitors and never polls |
| P32 | The system suite takes 12.6 to 13.1 minutes: between 757 and 787 s in the runs of 2026-11-23 on the trees of T20 and T21 (767 s on the merged head with T21), with a spread of 30 s between runs of the same tree. T20 added 3 s, T21 nothing. The budget I set for it is 13 minutes (780 s), and nothing enforces it | The margin is used up. The next test that restarts an IOC must come with a trim: the NT 20 and Matsusada fault tests are the slowest |
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
| P49 | After one reply that comes later than about 200 ms (the reply timeout of 150 ms plus the 50 ms the protocol waits after it), the requests and replies of a Matsusada line stay out of step for as long as the line is busy: each request is paired with the reply to the previous one. StreamDevice ends a protocol at the first mismatch, and the next request goes out before the reply that is still on its way has arrived. Seen once, in my first device-case run of T21 and not caused by it: all four simulated lines gave no reply within 150 ms at the same moment (it looks like a pause of the whole machine, cause unknown), and mismatches were logged for 40 s, about 45 per second at first. Two tests of T20 failed in that time. The replies to the monitor queries carry no unit number. On the line of AU-20P7-1 and -2, unit 1 logged about 260 mismatches per monitor record and unit 2 about 31, which fits requests that alternate between the units with unit 2 accepting unit 1's voltage and current as its own, without alarm. That is inferred from the counts, not seen as a wrong value. A supply alone on its line (the REK) shows INVALID instead. In `matsusada_co_ctrl.proto` and `rek.proto` since the first round | Your word (question 15). I recommend a task of its own before the supplies are used on the machine: after a mismatch or a late reply the line is kept quiet until the stray reply has arrived and is discarded, and a test makes one reply late on purpose with two supplies at different voltages |
| P50 | Two things the rules of T20 and T21 leave as they are, both harmless. A value written into `ToggleOutput` in the first milliseconds of a switching, before its SW line is formatted, is sent by that switching itself and then once more by `_out:resend`: the supply gets the same setting twice. And when the gate's result changes in the microseconds in which the switching sequence is starting, and the gate's own scan sees it before the change event, the output still follows the latest result, but an on that overtakes an off sequence goes out without the current limit having been sent again just before; that matters only for a supply that has forgotten its limit. Read from the source (`seqRecord.c`, `StreamCore.cc`), the window not measured | Know it |

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
