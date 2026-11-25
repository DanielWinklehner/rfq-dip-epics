You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T31: the owner changed where the vacuum gauges go, on 2026-11-25, while bringing the real system up. The system (rack IOC, emulation, plan, tests, GUI) must follow, so that he sees the six-way cross's pressure in the GUI's drawing while he pumps it down. His words:

- "slight change of plans: inficon foes on the roughing line (because it has a smaller flange than the others) and the APG and a regular AIM go on the 6-way. We defer the nAIM to later. both APG and AIM should be controlled by the TIC station"
- asked whether the homemade gauge box is out of the system with this: "Yes, drop it"
- "Inficon, AIMs (receptacle 2 on the TIC) and APG are connected to the respective controllers."
- "The AIMs may not be turned on until the APG shows 1e-2 Torr or lower"

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t31`, on branch `emu/t31-gauges-on-the-tic`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never touch `/home/daniel/code/rfq-dip-epics` itself or another worktree.
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04 with Python 3.10. `sudo` needs a password, so install nothing on the host. Docker works without sudo. Python tooling runs in the image `mist2-tools:dev`, the IOC in `mist2-ioc:dev`.
- The full emulation exists ONCE on this machine (Compose project `mist2emu`, GUI project `mist2ras`). This task needs it. Every command that starts or uses it goes through the lock: `flock /tmp/mist2emu.lock <command>` (`make -C emulation test` starts and stops the emulation itself; so does the GUI check, read its header). The lead does not use the emulation while you work. Do not change files the running emulation mounts (`EPICS/`, `plan/`, `emulation/sim/config`) while a run of yours is going. A device case (`emulation/devtest/run.sh <case>`) is its own project and needs no lock.
- Long commands exceed your tool's time limit (the system tests take 14 minutes, the GUI check several): run them in the background, write output and exit code to files in your own scratch directory, and look at the files in short steps. Do not use file names another agent could share.
- Your shell's working directory may reset between commands: start every command with `cd /home/daniel/code/rfq-dip-epics/.claude/worktrees/t31 && ...`.
- Some file tools refuse `.db` files as binary: read them with `cat`.
- Never run `rm` with a shell variable in its path. Never pipe a download into a shell. Leave no container and no process running when you finish (`docker ps` empty).
- The owner's name, e-mail address and project name go into no request to an outside service.
- `CLAUDE.md` at the top of the repository holds the owner's rules. A second Claude session works on the lab's computers and commits to `docs/emulation/STATUS.md` (its section "Seen on hardware, lab session") and `CLAUDE.md`: do not edit either file.

# Read first
1. `docs/emulation/STATUS.md`: answers 58 to 65, questions 23 to 25, open points P66 to P73, and the section "Seen on hardware, lab session" from "the TIC, first contact" upward (what the real TIC and the real VGC401 send).
2. `docs/emulation/TIC.md` and `docs/emulation/VGC401.md`, each with its section "Seen on the lab's controller"; `EPICS/Db/tic.db`, `vgc401.db`, `pressure.db`, `aim.db` (use `cat`).
3. `plan/controls.yaml`: the devices `gauge_ctrl`, `gauge_foreline`, `tic`, `naim`, `sensorbox` (how a device that left the system is kept: no load, `link: none`, its story in the notes), `turbo2` (flag `not_installed`); the sections `interlock`, `trends`, `logging`, `databases`; and `plan/build.py` enough to know what it checks.
4. How the emulation produces pressures: `emulation/sim/config/` (the rack's simulators and the plant model), `emulation/sim/mist2sim/` (the plant process and the device modules `libcom1`, `edwards_naim`, `edwards_tic`, `inficon_vgc401`), `emulation/sim/tests/test_plant_process.py`, `docs/emulation/DESIGN.md` on the plant model.
5. The rack IOC: `EPICS/ioc/iocBoot/iocRack/st.cmd`, `ports.sim.cmd`, `ports.real.cmd`; `EPICS/ioc/host/99-mist2-serial.rules`.
6. The system tests: `emulation/tests/README.md`, `system.py`, and every test that names a pressure PV or the simulators `gauges` and `aim`.
7. The GUI: `docs/emulation/gui/LAYOUT.md`, `RAS/mist2/ReactApp/src/config/drawings.json`, `src/registry.js`, the synoptic's code for gauges and for the title and banner, `RAS/mist2/tools/gui-check.sh` (header) and how the GUI was checked before (`docs/emulation/gui/`).

# Decided by the lead (do not change; if one cannot be built as written, stop and report)
D1. **The homemade gauge box is out of the system** (owner). The rack IOC no longer loads `pressure.db` and `libcom1_device.db` for `PRESSURE` on `AVR6`; port `AVR6` leaves both port files; the simulator `gauges` leaves the emulation's configuration; the udev rule line for `/dev/mist2/gauges` leaves the rule file, with one comment line that says so. In the plan `gauge_ctrl` is kept as `sensorbox` is: no load, its story in the notes. `EPICS/Db/pressure.db` and the device case `emulation/devtest/libcom1_devices` stay as they are. The PVs `PRESSURE:apg:*`, `PRESSURE:diag_box:*`, `PRESSURE:id` and the box's other records end by the owner's word; this is not a rename. `PRESSURE:foreline:*` (the VGC401) is untouched.
D2. **The nAIM stays loaded and flagged not installed** (plan 0.34 did that): nothing to do, but nothing may depend on its reading any more.
D3. **The six-way cross's two pressures are the TIC's:** the APG on socket 1 and a regular AIM on socket 2 (owner; both seen through the rack IOC on 2026-11-25). PV names stay `TIC:gauge<n>:*`: no alias, no new name (question 25 c is open).
D4. **The emulation follows:** the plant model's six-way cross pressure drives the simulated TIC's gauges 1 and 2, its foreline pressure drives the simulated VGC401, and socket 3 is empty. The simulated gauges behave as the real ones were seen to: the APG reports exactly 1.0000e+05 Pa at its top and exactly 1.0000e-02 Pa at its floor, always in the state On; the VGC401 with its PCG head. SEEN for the AIM on socket 2 at atmosphere: state 5 "Off", units type 59, alert 0, priority 0, and so `TIC:gauge2:getpressure` INVALID with the state "Off". The owner's rule: the AIM may not be on until the APG shows 1e-2 torr (1.33 Pa) or lower. NOT SEEN: who switches it on (the TIC by a setup of its own, D397-30-880 Table 1 object 914 "slave setup", or the owner at the panel), the state while it strikes, and the pressure at which it goes off again. The simulated TIC switches socket 2 by socket 1's value: on at or below 1e-2 torr, through the state 6 "Striking" for a short time, off above a second value; both pressures and the striking time are named configuration values, the on value from the owner's rule, the other two ASSUMED. List them in your report. Whatever in the emulation read the old gauge box or the nAIM for its physics or its permits (find it) reads the new sources or is reported to the lead.
D5. **With an empty socket 3, `TIC:gauge3:*` is INVALID for good.** The system tests expect every PV valid while nothing is at fault. Solve it in the plan and the registry, not in the tests: a channel that is known to be empty is marked so in the plan (propose the smallest form; the device flag `not_installed` is the model) and is then treated by the registry, the tests and the GUI as an uninstalled device is. If that needs more than a small change of `plan/build.py`, `plan/registry.py` and the GUI's registry code, stop and report the options.
D6. **The GUI's drawings:** wherever a drawing shows the homemade box's APG on the six-way cross it shows the TIC's gauge 1; wherever it shows the nAIM there, the TIC's gauge 2; the foreline gauge (`gauge_foreline`) gets a gauge symbol and tag on the foreline of the turbopump. Nothing else moves. The TIC station's pumps get no symbol in this task.
    The AIM is off most of the time at rough vacuum, and its pressure is INVALID then, which is right. The operator must see why: where a gauge's pressure is INVALID and its channel has a state, the tag shows the state's word ("Off", "Striking", "Gauge Not connected", and for the foreline gauge "Underrange" beside its value). If the gauge's tag cannot take a second role without a rebuild of the widget, stop at that point and report what it takes.
D7. **Title and banner (open point P68):** with the rack IOC on real hardware the browser's title said "[SIM] MIST-2", and with no IOC connected the banner said "EMULATOR". Wanted: "[SIM]" and "EMULATOR" only when an IOC reports the emulation's mode and none reports real hardware; real hardware on every connected IOC: no "[SIM]" and no banner of the emulation; a mix: the mixed banner as today, and a title that is not "[SIM]"; an IOC whose mode is not known is named as such and does not make the system an emulator. Read how the mode reaches the GUI before you change it.

# What to build
R1. The rack IOC, the rule file and the simulator's configuration after D1 and D4.
R2. The plan (`plan/controls.yaml`, one new revision with its note; `python plan/build.py` without warnings), the registry and `plan/out` regenerated (`flock /tmp/mist2emu.lock sh -c 'make -C emulation registry && make -C emulation plan && make -C emulation plan-check'`), after D1, D3 and D5. Remove what named the old box (the logging rule for `PRESSURE:diag_box:getpressure`, labels, trends); change the interlock table's and the work packages' words where they name the old sources.
R3. The plant model's coupling after D4, with unit tests of the simulator side (the APG's floor and top, the AIM's switching, the VGC401's range).
R4. The system tests pass with every PV of the new arrangement covered as the others are (read, fault lists, update rate). If a test named the old gauge box or the nAIM, it now names the new source; say which tests changed and why.
R5. The GUI after D6 and D7, checked with the GUI check the repository has (headless), with screenshots of the pages you changed in your report's list of files (path and what it shows).
R6. `docs/emulation/LAB-SETUP.md`: the device table and the text that named the gauge box and the nAIM as devices to connect, after D1 to D3. No other document: the lead writes STATUS.md.

# Tests
1. `flock /tmp/mist2emu.lock sh -c 'make -C emulation registry && make -C emulation plan && make -C emulation plan-check'`: no warning, exit code 0.
2. `emulation/sim/run_tests.sh`; the device cases `emulation/devtest/tic`, `emulation/devtest/vgc401`, `emulation/devtest/libcom1_devices`.
3. `flock /tmp/mist2emu.lock make -C emulation test`: all pass. Give the count before (296 passed, 2 deselected) and after, and explain the difference.
4. The GUI check, through the lock. See it fail once for D6 (a drawing entry that names a device that no longer exists) and once for D7.
5. The rack IOC starts with the real port file in a container without devices and reaches "iocRun: All initialization complete" (how: `docker run --rm --init --network none -e MIST2_PORTS=real -e MIST2_SAVE=/tmp/save -v "$PWD/EPICS/Db:/opt/mist2/EPICS/Db:ro" -v "$PWD/EPICS/ioc/iocBoot:/opt/mist2/EPICS/ioc/iocBoot:ro" mist2-ioc:dev iocRack real`, stopped by `timeout 35`), with no line about `AVR6` or `PRESSURE:apg`.

# Files you own
`EPICS/ioc/iocBoot/iocRack/st.cmd`, `ports.sim.cmd`, `ports.real.cmd` (only the lines of D1; the TIC block's device name was set by the lab session from the real computer: do not touch it), `EPICS/ioc/host/99-mist2-serial.rules` (the one line), `emulation/sim/config/**`, the plant coupling in `emulation/sim/mist2sim/**` with its unit tests, `plan/controls.yaml`, `plan/build.py`, `plan/registry.py`, `plan/test_build.py`, `plan/out/**`, `RAS/mist2/ReactApp/src/**` (drawings, registry code, title and banner; `registry.json` is generated), `emulation/tests/**`, `docs/emulation/LAB-SETUP.md`, a short note for the GUI under `docs/emulation/gui/` if its documents name what you changed. Not yours: `docs/emulation/STATUS.md`, `CLAUDE.md`, `EPICS/Db/*.db` and `*.proto` (if one of them must change, stop and report), everything else.

# Acceptance (the lead runs these from your worktree)
    flock /tmp/mist2emu.lock sh -c 'make -C emulation registry && make -C emulation plan && make -C emulation plan-check'
    emulation/sim/run_tests.sh
    emulation/devtest/run.sh emulation/devtest/tic
    emulation/devtest/run.sh emulation/devtest/vgc401
    flock /tmp/mist2emu.lock make -C emulation test
    the GUI check (name the exact command in the report)
    the start of the rack IOC with the real port file (test 5)
All exit 0 (test 5: stopped by the timeout after the IOC finished its start).

# Rules
- Do not invent facts. What the real controllers send is in STATUS.md and the two documents; what a manual says has its place named; what neither says is a configuration value, named as assumed.
- No change outside the files you own. If something here turns out wrong or cannot be built as described, stop and say so in the report instead of building something else.
- A report that says "done" is not evidence: give the commands you ran, their exit codes and the numbers they printed, and say plainly what you did not do or could not show.

# Final report, with these headings
MODEL, BRANCH, BUILT (by R1 to R6), WHAT READ THE OLD GAUGES AND WHAT IT READS NOW, THE EMPTY SOCKET (D5: the form in the plan and what treats it how), VERIFIED (commands, exit codes, counts, how each test was seen to fail), DECISIONS (with reasons), ASSUMED (each with the configuration value that holds it), NOT VERIFIED, QUESTIONS FOR THE OWNER, NEEDS THE LEAD (text for STATUS.md).
