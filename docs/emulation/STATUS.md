# Status

Last update: 2026-11-21. **G1 is approved** (D1 to D8 as proposed in [DESIGN.md](DESIGN.md)).
**G2 is open**: the layout proposal [gui/LAYOUT.md](gui/LAYOUT.md) waits for your choice.
All device tasks (T3 to T6) and T1, T2, T9, T10 and T14 are merged, and **every device of the
table is loaded by the two emulated IOCs (T7 done)**. Running: T8 (system test suite), a
follow-up of T3 on even polling, and a follow-up of T10 on the database parser.

## Done

- Branch `emulated-iocs` created from `origin/libcom1-robustness-fixes` (`99beb4f`). Nothing pushed.
- `plan/` added from `mist2-controls.zip` (revision 0.6). `plan/build.py` runs without warnings
  in a container: 27 devices, 86 existing PVs, 44 proposed PVs, 9 sketches.
- `reference/lab-2023/` added from `latest.zip`.
- Read: repository documentation, all databases and protocol files, libcom1 README, tests and
  device sketches, `RAS/IsoDAR`, the plan, the 2023 lab snapshot.
- Checked against manuals:
  - Leybold NT 20 operating instructions GA 05.208/8 (remote inputs, relays, RS-232).
  - Matsusada CO series manual rev 0.4 (reply formats, `#AL`, sets are unanswered).
- Checked on this machine: Docker 29.9.2 and Compose 5.6.1 work without `sudo`, RAS tag
  `V8.1.0` and the example project are reachable.

- **T1 merged** (acceptance sequence run by the lead): image `mist2-ioc:dev` with EPICS base
  R7.0.10, asyn R4-46 and StreamDevice 2.8.26, the EPICS top `EPICS/ioc` with one `st.cmd` and
  two port files per IOC, `emulation/compose.yaml` with two IOCs at `172.30.0.11` and `.12`, the
  Channel Access proof and the device test harness. `make -C emulation build up ca-proof down`.
- **Channel Access proof, 16 checks, all pass**: both IOCs answer a broadcast from the bridge
  network and from the WSL host network, and each answers a unicast search for its own PVs only.
- **T2 merged** (acceptance test run by the lead): simulator core and libcom1 simulator. The
  Python libcom1 engine gives the same 122-line transcript as the real library for
  `AVR/libcom1/tests/script.hpp`, in the AVR and in the `%g` number format.
- **pvServer proof against the emulated IOCs passed**: the RAS pvServer reads heartbeat and mode
  of both IOCs on `172.30.0.0/24`.
- **T10 merged** (checked by the lead, including three negative checks): `plan/controls.yaml`
  is revision 0.7 and describes what was built. `make -C emulation plan-check` now compares the
  plan with the databases and both `st.cmd` files and fails on any difference. The device
  registry `RAS/mist2/ReactApp/src/registry/registry.json` is generated from the same sources:
  19 devices, 2 IOCs, 219 PVs, 15 simulators. `plan/out` keeps only the PDFs and the Word file
  under version control (D8), `plan/epics_db` is gone.
- **T7 done** (by the lead): `make -C emulation up` starts two IOCs and two simulator containers
  with every device. Both IOC logs are free of errors. Checked by hand on the running system:
  a PV of every device, high voltage on with read-back, the interlock door switching off the AU
  supplies (rack IOC) and the REK (platform IOC, through Channel Access between the IOCs), and
  "all off".
- **T3 merged** (acceptance run by the lead: 74 unit tests, 22 device tests): `matsusada_co`
  bus simulator, `matsusada_au20p7.db`, `rek.db`, `au_alloff.db`. Lab PV names kept. New PVs:
  `AU:alloff:set` and, per supply, `:output:init` (internal).
- **T5 merged** (acceptance run by the lead: 9 MFC, 6 Faraday cup, 9 turbopump tests):
  `mfc.db`, `faradaycup.db`, `turbo.db`, `turbo_pump.db`, `nt20_monitor.db` with their protocol
  files and simulators. The MKS RS-485 supplement (1046411-001 Rev. A) was found, so the MFC
  protocol is from the vendor's document. New PVs: `MFC:getFlow`, `FC:current:get`, and the
  `TURBO1:*` and `TURBO2:*` sets of the G1 note.
- **T4 merged** (acceptance run by the lead: 13 TDK tests, 11 nAIM tests): `tdk.db` and
  `aim.db` on the lab's names. New PVs: `TDK:power:get`, `TDK:mode:get`, `TDK:fault:get`.
  All three TDK sets and the nAIM enable are acknowledged, and a missing or negative answer
  ends in an alarm. The TDK recovers by itself after a power cycle (1.4 s in the test).
  TDK update rate: predicted 10.0 Hz, measured 9.6 Hz by Channel Access.
- **T6 merged** (acceptance test run by the lead, 81 tests): `thermocouples.db`,
  `solenoidbox.db`, `pressure.db`, `sensorbox.db` and `interlockbox.db` carry the lab's names
  and meanings and keep this branch's acknowledged sets, identity and alarm propagation.
  New PVs: `THM:j<n>:get` and `THM:f<n>:get`. A faulted thermocouple now reads INVALID.
- **T9 merged** (acceptance test run by the lead): `RAS/mist2/` is a running application shell
  on RAS V8.1.0 (submodule). `make -C RAS/mist2 dev-up`, then `http://localhost:3000/` in the
  Windows browser. Three containers (nginx, Vite, pvServer), no database: with login disabled
  the pvServer does not need MongoDB.
- **Proven**: a pvServer on the host network reads PVs from IOCs on a Docker bridge network
  through the subnet broadcast address. Shown with stand-in IOCs on `172.31.0.0/24`. The same
  check against the emulated IOCs follows when T1 is merged (`RAS/mist2/tools/pv-proof.sh`).
- **T14 merged**: three layout options with wireframes in `gui/`.

## Open

- G2: choice of the GUI layout, and the questions about the machine in gui/LAYOUT.md section 6.
- Everything in [PLAN.md](PLAN.md) from T1 on, except T14.
- Briefs for T8 (system tests) and T10 (plan and registry) are written. T10 starts when T3 is
  merged, T8 after T10, because the tests take their PV names from the registry.

## Subagents

- All subagents report the model ID `claude-opus-5-5`.
- The Agent tool's own worktree isolation cuts worktrees from `master`, not from the current
  branch. The first four subagents noticed this at their setup check and stopped without
  changing anything. The lead now creates each worktree from `emulated-iocs` under
  `.claude/worktrees/<task>` (ignored by git) and names it in the brief.

## Decisions taken, with reasons

| Decision | Reason |
|---|---|
| `plan/` committed in two commits: sources, then `out/` | `out/` is 10 MB of generated files. Whether it stays under version control is D8, and a separate commit is easy to drop before the first push |
| `latest.zip` committed as `reference/lab-2023/`, not merged into `EPICS/Db` | It is a 2023 state and the lab has moved on. Subagents in worktrees can read it, and the merge into `EPICS/Db` happens per device with a visible diff |
| `plan/build.py` and all tooling run in containers | `sudo` needs a password, and Graphviz, python-docx and pytest are not installed on the host |
| Simulators in their own containers | See DESIGN.md section 2 |
| EPICS base R7.0.10, not R7.0.11 | StreamDevice 2.8.26, the latest release, does not build against R7.0.11. The fix is on StreamDevice's master branch but in no release. With R7.0.10 everything is an unmodified release tag |
| Each port file starts with the line `on error break` | Without it an error inside a file loaded with `iocshLoad` is ignored and the IOC starts half-configured. It is the one line in the port files that is not port configuration |
| An IOC with an unset or wrong `MIST2_PORTS` exits instead of starting | A real computer must never come up on simulator ports by accident, or the other way round |

## Assumptions that need your confirmation

"Lab files" means the current databases, protocol files, both `st.cmd` and `dbl` output from
both IOCs, expected in the week of 2026-11-23.

| # | Assumption | Source | Settled by |
|---|---|---|---|
| A1 | The lab's PV names are those of the 2023 snapshot | `latest.zip`, lab GUI | Lab files |
| A2 | AU units: 1 source, 2 puller, 3 lens 1, 4 lens 3, 5 lens 2 | 2023 `st.cmd` for 1 to 4, unit 5 is a guess | Lab files, front panels |
| A3 | Source and puller on the USB-OPT chain, lenses on the CO-U32 chain | Prompt, plan | You |
| A4 | AU20P15: 20 kV and 15 mA full scale, same 16-bit set and 12-bit monitor scaling as the P7.5 | Model name. The local scaling fix is not in `latest.zip` either | Lab files |
| A5 | Negative supplies show positive numbers | 2023 database has no sign handling | You (D3) |
| A6 | Turnaround time of the Matsusada adapters: 5 ms in the simulator | Not in the manual | Measurement on hardware |
| A7 | REK150-24 on its own port, unit 1, 9600 baud | Repository `st.cmd` | Lab files |
| A8 | TDK at address 6, 19200 baud | `tdk.proto`, repository `st.cmd` | Lab files |
| A9 | Thermocouple board at 19200 baud | Firmware says 19200, both `st.cmd` say 9600 | Lab files |
| A10 | Gauge controller at 115200 baud, no parity | Firmware. Both `st.cmd` say even parity | Lab files |
| A11 | MFC at address 254, 9600 baud. The snapshot's files are a draft: set point only, no flow read-back, commented out in `st.cmd` | `latest.zip` | Lab files |
| A12 | `MFC:getFlow` as the name of the flow read-back | My proposal in the lab's style | Lab files |
| A13 | Faraday cup Opta speaks libcom1 over TCP and serves one current channel. The cup actuator is valve channel s4 | Lab GUI labels s4 "Faraday Cup" | Firmware source |
| A14 | One valve box with 8 channels: s1 foreline valve, s2 MFC shutoff, s3 vent valve, s4 Faraday cup | Lab GUI | You |
| A15 | nAIM answers `!C752` as in the Edwards manual. The pressure is in torr | Snapshot database says torr | Lab files, manual |
| A16 | Both NT 20 have the RS-232 port fitted. One Opta drives both, wired as "ON/OFF switch" (Fig. 6) | Manual lists the port without calling it an option | You, rear panels |
| A17 | NT 20 RS-232 record format is unknown. Simulator and parser use an invented format | Manual: "more details on request" | A capture from a unit |
| A18 | Sensor box and old interlock box are still connected to the rack IOC | 2023 `st.cmd`. Not in your device table | You (D5) |
| A19 | The AU and REK output gate on `interlock_open` is still wanted | 2023 databases | You |
| A20 | Emulation subnet `172.30.0.0/24`. Nothing depends on the switch model or the real address plan | Free choice | You, if it collides with a network of yours |
| A21 | Linux device names in `ports.real.cmd` are placeholders (`/dev/mist2/<name>`) | udev rules do not exist yet | Work package WP4 |
| A22 | The platform IOC runs the same EPICS top as the rack IOC | Its operating system and `st.cmd` are unknown | Lab files |

## Open points from the device tasks

| # | Point | Needs |
|---|---|---|
| P1 | Done: `<DEVICE>:channels` is a long-string record with up to 255 characters. A client reads the whole text from the field `VAL$` (`caget -S THM:channels.VAL$`). A plain read of `THM:channels` still ends after 39 characters, which is a limit of Channel Access strings. `id` and `firmware` are still limited to 39 characters, and no device comes near that | Closed |
| P2 | Which gauge controller firmware runs in the lab: `IonGaugeController` (Arduino Mega, 8N1) or `IonGaugeController_Teensy`? The lab's `st.cmd` calls it a Teensy and sets even parity. The emulator follows the Mega sketch | You |
| P3 | Unit of the sensor box water flows. The sketch's factor 0.06 fits litres per hour by one comment and not litres per minute by the other. The unit field is left empty | You |
| P4 | The interlock box has two relay channels (`s1`, `s2`) that no database uses. What do they switch? | You |
| P5 | The door PVs `INTLK:i1:get_interlock` and `i2` are binary records with the states Open and Closed now. The lab's were analog records with the same numbers (1 = closed). A client that reads the number sees no difference, a client that reads the type does | You, if a script depends on it |
| P7 | The nAIM instruction manual was not found. Its protocol (`?V752` answered by pressure and a 4-digit hexadecimal status word, `!C752` answered by `*C752 0`) is taken from INFICON's description of the "Edwards nAIM protocol" (tira83e1-e) and from the Edwards TIC manual for the message structure. To be checked on the gauge | You, with the gauge |
| P8 | The nAIM reports in the unit configured in the gauge (status bits 4 and 5). The lab's database says torr and nothing checks it | You, with the gauge |
| P9 | `AIM:getpressure` is INVALID while the gauge is off or striking, by decision of T4 from the status word. It keeps the number the gauge sent | Tell me if you prefer another display |
| P10 | After a TDK power cycle the supply comes back with its output off (safe start), while `TDK:status:setpoint` still shows ON until it is written again. `TDK:status:get` shows the truth | GUI and loop design |
| P11 | MFC: the supplement does not show the reply to a set (with or without the value) or a literal example of a negative reply. The protocol file accepts both forms of the positive reply. `MFC:getFlow` reads in flow units (sccm), the set point stays in percent of full scale as in the lab's draft | Lab files |
| P12 | Faraday cup: everything but the hardware is assumed (libcom1 over TCP, one channel in A, identity `FaradayCupOpta`) | Firmware source |
| P13 | Turbopump Opta: its firmware does not exist. The channel map is defined in `turbo.db` (`r1 r2 r3 r4 n1 a1 f1 n2 a2 f2`), and the firmware has to be written to match | Firmware, later |
| P14 | NT 20 monitor port: the record format is invented (`NT20 f=0833Hz I=1.25A ACC`). `TURBO<n>:raw:get` and `:age:get` work with any one-line format | A capture from a unit |
| P15 | The simulator's `close` fault accepts and closes every reconnect, which makes an IOC with `@init` handlers log about 100 lines per second while the fault lasts. Planned: stop listening instead | Lead, after T3 |
| P16 | **Outputs come back on by themselves.** When the interlock opens, the AU and REK outputs are forced off, but the request stays set. When the interlock closes again, the outputs switch back on without anyone doing anything. That is how the lab's 2023 database works, and I kept it. Your interlock rules in the plan say that a trip latches. One record more would clear the request on permit loss | You |
| P17 | **Enabling an output sets the current limit to 100 %.** The lab's sequence sends `ICN 100` on enable, so `current:setpoint` is overwritten: I set 10 mA, enabled, and the echo read 15 mA. Kept, with the percentage as macro `ICN_ON` | You |
| P18 | **Update rates on a chain are uneven.** With two supplies on a chain the first one gets about 9 Hz and the second one 5 to 9 Hz, at 16 ms turnaround 8 Hz and 5 Hz. Cause: each monitor record is scanned at 10 Hz on its own, and a record that is still waiting for the line misses its turn. The bus arithmetic assumes an even share. Follow-up given to T3: poll each chain in one fair round | T3 follow-up |
| P19 | The supplies are put into remote mode (`REN`) with every status poll, so that a supply that was switched off and on comes back by itself. Side effect: the front panel cannot take local control while the IOC runs. The lab sent `REN` only at start and on switching | You |
| P20 | A set-point write in the first 5 s after an IOC start is not sent to the supply (the databases first take over the supply's own settings, so that a restart changes nothing) | Know it |
| P21 | Simulator core, wishes from the device tasks: several input terminators, line settings changeable at run time, transaction counts per command, and P15 | Lead, later |
| P22 | The database parser of `plan/build.py` does not see a record that is written on one line, so such a record would be missing from plan and registry without a warning. No database in the repository has one. Follow-up given to T10 | T10 follow-up |
| P23 | `make -C emulation plan` changes the tracked PDFs and the Word file on every run, because the tools embed the build time | T10 follow-up, optional |
| P6 | The gauge controller keeps sending the last pressure after a gauge is switched off. A pressure value does not prove that the gauge is on | Firmware, later |

## Found in RAS V8.1.0

- No RAS component colors severity INVALID. `TextOutput`, `TextInput` and the others handle
  MINOR and MAJOR only, so an INVALID record shows its last value in plain style. The new GUI
  needs its own thin wrappers for this. A lost Channel Access connection is handled by RAS.
- The pvServer sends severity and time stamp but not the alarm status (STAT). The expert pages
  read `<record>.STAT` as a PV of its own.
- The boilerplate has no lock file for its Node packages, so the frontend image is not exactly
  reproducible from one build to the next.

## Found while reading, not yet acted on

- The lab's `toggle_output` sends `ICN 100` when an AU or REK output is enabled. That sets the
  current limit to 100 % of full scale, whatever `current:setpoint` holds. T3 keeps the behaviour,
  makes the percentage a macro and documents it in a test. Whether it is wanted is your call.
- The lab's and this branch's interlock databases disagree in their comments on which input
  value means "door closed". T6 settles it from the firmware.
- New PVs that were not in the G1 note: `IOC-RACK:heartbeat`, `IOC-RACK:mode` and the same for
  `IOC-HV`. `mode` shows `sim` or `real`, so that the GUI can label the emulator on every page.

- `thermocouples.db` exposes 4 of the board's 16 channels. Junction temperatures and fault
  codes have no PVs (proposal in DESIGN.md).
- `rek.db` labels the current read-backs mA, the values are in A.
- The CO manual says a supply sends an unsolicited `!` when its output is off or its power is
  off (RS-232, RS-485 and USB adapters). The protocol files do not expect it. The simulator
  gets a switch for it, default off, until it is seen on hardware.
- `plan/controls.yaml` assumes unit 2 is lens 1. The 2023 `st.cmd` says unit 2 is the puller.
- `plan/build.py` reads the snapshot in `plan/epics_db/`. Inside this repository it should read
  `EPICS/Db`, otherwise new databases never show up as existing.
- The plan proposes `REK-1:mode:read` and `REK-1:alarm:read`. The CO protocol has no command
  for either.
