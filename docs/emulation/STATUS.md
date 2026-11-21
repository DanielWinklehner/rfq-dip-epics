# Status

Last update: 2026-11-21. **G1 is approved** (D1 to D8 as proposed in [DESIGN.md](DESIGN.md)).
**G2 is open**: the layout proposal [gui/LAYOUT.md](gui/LAYOUT.md) waits for your choice.
T1, T2, T6, T9 and T14 are merged. The device tasks T3, T4 and T5 are running, one subagent
and one worktree each.

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
- Briefs for T3 to T6 are written (`briefs/`). They start when T1 and T2 are merged.

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
| P1 | `THM:channels` is cut after 39 characters: the thermocouple board's list of 16 channels has 47. The limit is in `libcom1.proto` and `libcom1_device.db` (a string record). Fix planned after T3 to T5 are merged | Lead |
| P2 | Which gauge controller firmware runs in the lab: `IonGaugeController` (Arduino Mega, 8N1) or `IonGaugeController_Teensy`? The lab's `st.cmd` calls it a Teensy and sets even parity. The emulator follows the Mega sketch | You |
| P3 | Unit of the sensor box water flows. The sketch's factor 0.06 fits litres per hour by one comment and not litres per minute by the other. The unit field is left empty | You |
| P4 | The interlock box has two relay channels (`s1`, `s2`) that no database uses. What do they switch? | You |
| P5 | The door PVs `INTLK:i1:get_interlock` and `i2` are binary records with the states Open and Closed now. The lab's were analog records with the same numbers (1 = closed). A client that reads the number sees no difference, a client that reads the type does | You, if a script depends on it |
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
