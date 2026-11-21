# MIST-2: emulated IOCs and a new RAS front end

You are the lead engineer for this task. You plan, delegate, review and integrate. The implementation work goes to subagents that run on Opus 5.5.

## Goal

In the repository `DanielWinklehner/rfq-dip-epics`, on a new branch `emulated-iocs` created from `origin/libcom1-robustness-fixes` (commit `99beb4f`), build two things:

1. **Two emulated EPICS IOCs** that behave like the two real control computers of the MIST-2 ion source, with every device replaced by a software simulator.
2. **A new React Automation Studio (RAS) front end** that runs against them.

The purpose is to develop and test databases, GUI and (later) control loops at a desk, without the ion source. Whatever runs against the emulator must later run on the real IOCs with nothing changed but the port configuration.

## How to work

- **Read first:** `README.md`, `EPICS/README`, `EPICS/st.cmd`, everything in `EPICS/Db`, `AVR/libcom1/README.md`, `RAS/README.md`, `RAS/IsoDAR/`, and the planning folder `plan/` (see Context). Then write `docs/emulation/PLAN.md`: tasks, dependencies, and which subagent gets what.
- **Delegate:** give each task to a subagent through the Agent tool with model `opus` (Opus 5.5). If you cannot select the model, tell me before you start. A subagent starts with no context, so every brief must stand alone: goal, the files it owns, the interfaces it has to respect, the acceptance test, and what to report back.
- **Parallel where independent:** use separate git worktrees so that two subagents never edit the same files. Integrate one result at a time.
- **Verify yourself:** run each acceptance test yourself before you accept a result. A report that says "done" is not evidence.
- **Keep `docs/emulation/STATUS.md` current:** done, open, decisions with their reasons, and every assumption.
- **Git:** small commits with clear messages, never on `master`. Do not push and do not open a pull request until I say so.
- **Do not invent facts.** If a protocol detail, a unit number or a PV name is unknown, make it a configuration value, record the assumption, and ask.
- **Three gates where you stop and wait for me:**
  - G0: the startup questions at the end of this prompt.
  - G1: a short design note (emulation architecture, PV names for devices that have none yet, the NT 20 interface).
  - G2: the GUI layout proposal.

## Context

**The real system.** Two IOCs (EPICS, asyn, StreamDevice), a GUI server, and a new Ethernet switch with fiber links to both IOCs. The rack IOC runs Windows today and moves to Linux. The platform IOC sits on a high-voltage platform, so fiber is the only connection to it. The target for both is Linux, and that is what you emulate.

**The repository.**
- `EPICS/Db` holds the databases and StreamDevice protocol files. `EPICS/st.cmd` is an old single-IOC Windows startup file with COM ports. Use it as the record of which database belongs to which device, not as a model.
- `AVR/libcom1` is our Arduino communication library. The branch you start from added protocol 2: acknowledged sets (`S...` answered by `ok`), an identity query (`I`), and alarm propagation in the databases. `AVR/libcom1/README.md` documents the protocol and `AVR/libcom1/tests` builds the real library on a PC.
- `RAS/IsoDAR` is the existing GUI code. It dates from 2021 and contains many placeholder PVs (`testIOC:...`).

**The plan.** Before anything else, copy the planning folder into the repository as `plan/` and commit it (I will tell you where `mist2-controls.zip` is). `plan/controls.yaml` is the single source of truth for devices, connections, PVs and open questions. `python plan/build.py` regenerates the sketches and the Word document. Keep it current: when a device gets a database, update the YAML so that its PVs show up as existing.

## Deliverable 1: the emulated IOCs

### Devices

| IOC | Device | Protocol and files | Notes |
|---|---|---|---|
| platform | Thermocouple board (Arduino) | libcom1, `thermocouples.db`, `libcom1_device.db` | PVs `thm:*` |
| platform | TDK-Lambda GENESYS 8-300, filament heating | `tdk.proto`, `tdk.db` | PVs `tdk:*` |
| platform | Matsusada REK150-24, filament discharge | `rek.proto`, `rek.db`, unit 1 | PVs `REK-1:*`. A REK150-55 replaces it soon: make full-scale voltage and current macros |
| rack | 5 x Matsusada AU with CO-HV on two optical chains | `matsusada_co_ctrl.proto`, `matsusada_au20p7.db` | See below |
| rack | MKS GV50A mass flow controller | MKS RS-485 multi-drop | Works in the lab, but its protocol file and database are not in the repository. Ask me for them (G0) |
| rack | Solenoid valve controller (Arduino, 8 channels) | libcom1, `solenoidbox.db`, acknowledged sets | PVs `avr12:*`. Moves to an Arduino Opta over TCP later, same PVs |
| rack | Vacuum gauges | `pressure.db` (homemade APG/AIM controller, libcom1) and `aim.db`/`aim.proto` (Edwards nAIM) | The homemade controller will be replaced later, probably by an Edwards TIC. Emulate today's devices, keep the simulator easy to swap |
| rack | Faraday cup readout (Arduino Opta) | unknown | Firmware and PVs are not in the repository. Ask me (G0) |
| rack | 2 x Leybold TURBOTRONIK NT 20 turbopump controllers | new | See below |

**AU supplies.** Roles: AU20P15 ion source voltage, AU20N7.5 puller, AU20P7.5 lens 1, AU20N7.5 lens 2, AU20P7.5 lens 3 (installed, not in use, do not poll it). Two chains: source and puller on one adapter (USB-OPT), the lenses on the other (CO-U32). The CO protocol returns one value per request and all supplies of a chain share one 9600 baud line, so the update rate falls with every supply. Rework the database accordingly: poll only the monitors (`MN1`, `MN2`) fast, read the set-point echoes after a set and every few seconds, status once a second, `PRIO = HIGH` on set records, full scale and polarity as macros (the P15 has 15 mA), one "all off" PV using `#AL`. Unit numbers are a G0 question.

**Leybold NT 20.** What I know from the operating instructions (GA 05.208): the unit has remote-control inputs for start and stop, and an RS-232 port that only reports (internal values, sent about every 8 s, format not published). I expect status relays for normal operation and failure, as on its sister models, but have not confirmed them. Proposed solution, which you should check against the instructions and confirm or correct at G1: an Arduino Opta drives the remote inputs and reads the relays (libcom1 over TCP), and a listen-only StreamDevice port reads the RS-232 records. Until I can capture real RS-232 output, treat its format as unknown and keep the parser isolated.

### Requirements

- **Same files for real and emulated.** Databases and protocol files are shared. Each IOC has one startup file that includes a port file for the chosen mode: simulator ports are TCP (`drvAsynIPPortConfigure`), real ports are serial devices or TCP. Nothing else may differ.
- **Do not rename existing PVs.** For devices without PVs, propose names at G1.
- **Simulators** are small Python programs, one per bus or device, that speak the real wire protocol:
  - A bus simulator (Matsusada chain, RS-485) answers for several unit addresses.
  - Delay each reply by the time its characters would take at the real baud rate plus a configurable turnaround time, so that polling rates in the emulator match reality.
  - Values behave plausibly: set points are followed with a time constant, read-backs carry a little noise.
  - Every simulator can be told to misbehave (stop answering, close the port, answer garbage, trip) through one common control interface that the tests use.
  - Check the libcom1 simulator against the real library: replay the scripted conversation of `AVR/libcom1/tests` against both and compare the replies.
- **A simple plant model** behind the simulators is welcome as a second step (filament current drives discharge current with a thermal lag, gas flow and pumps drive pressure). Design the simulators so that it can be added without rewriting them. It will be the test bed for control loops.
- **Two computers, not two processes that happen to share one.** Preferred: Docker Compose inside WSL2, one container per emulated computer, each with its own IP address, built from one image that contains EPICS base, asyn, StreamDevice and the IOC application. Native processes in WSL are acceptable if you can show why they are better. Know the trap: two IOCs on one host do not both receive unicast Channel Access searches.
- **One command to start everything, one to test it.**

## Deliverable 2: the RAS front end

- RAS is at release 8.1.0 (May 2026). Custom applications start from the boilerplate `React-Automation-Studio-Example-Project-1`, which pulls RAS in as a git submodule. Propose at G1 where the application lives (this repository or its own).
- RAS's Docker setup expects Linux with host networking, and its README advises against other platforms. Run it inside WSL2 and open it from a browser on Windows. Verify that the pvServer container can read a PV from each emulated IOC before you build anything on top.
- **Layout proposal first (G2).** Study `RAS/IsoDAR`, then give me two or three layout options as wireframes with a recommendation. What I want from the new layout:
  - one overview page that shows the source as a synoptic, with live values where they are measured,
  - one page per subsystem (plasma generator, extraction, vacuum and gas, cooling, diagnostics),
  - expert pages one click behind (raw channels, firmware identity, communication state),
  - color that follows EPICS alarm severity instead of thresholds coded into pages.
- **Streamlined code.** One device registry generated from `plan/controls.yaml` instead of PV names scattered through components. One reusable widget per device class (power supply, valve, gauge, pump). No placeholder PVs, no dead code. Keep what is good in the existing pages, including their general look.
- Later additions that you should leave room for but not build: a printout of all values as one PDF, data logging with retention tiers, control loops (chapter 5 of the plan document).

## Done means

- `docs/emulation/README.md` explains how to start, stop and test everything on a fresh WSL2 Ubuntu.
- Both IOCs start without a single database or protocol error.
- An automated test reads every PV of every device, writes every set point and sees the read-back follow, and confirms that a set that gets no acknowledgement ends in an alarm.
- Fault injection works: a silent simulator turns the PVs of that device INVALID within seconds, and they recover without restarting the IOC.
- With five AU supplies on two chains, the measured update rate of the monitor PVs is reported and matches the bus arithmetic.
- The new GUI runs against the emulator, shows every device, and reflects alarm state.
- `plan/controls.yaml` matches what was built, and `python plan/build.py` runs without warnings.
- `docs/emulation/STATUS.md` lists every assumption that still needs my confirmation.

## Out of scope

The interlock system (it comes next), anything that needs real hardware, the Linux driver question for the Matsusada USB adapters, the replacement of the gauge controller, the dipole scan and the emittance scanners.

## Startup questions (G0)

Ask me these in one batch before you delegate anything, and tell me what you will assume if I do not know:

1. Where is `mist2-controls.zip`?
2. Is the GUI that runs in the lab newer than `RAS/IsoDAR` in the repository? If so, I will give it to you first.
3. The protocol file and database of the mass flow controller that work in the lab today.
4. The Faraday cup Opta: firmware source and PV names.
5. Unit numbers of the five AU supplies, and the local scaling fix for the AU20P15 that never reached the repository.
6. Is the RS-232 port fitted on the two NT 20 units, and which pumps do they drive?
7. Model of the new Ethernet switch and any IP address plan.
8. May you install packages and Docker inside WSL (sudo)?
