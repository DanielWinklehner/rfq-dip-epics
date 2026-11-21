# Status

Last update: 2026-11-21. **G1 is approved** (D1 to D8 as proposed in [DESIGN.md](DESIGN.md)).
Phase A is running: T1, T2, T9 and the layout study, one subagent and one worktree each.

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

## Open

- Everything in [PLAN.md](PLAN.md) from T1 on. Next gate: G2, the GUI layout proposal.
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
