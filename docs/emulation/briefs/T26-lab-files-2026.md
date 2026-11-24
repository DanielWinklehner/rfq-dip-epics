You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T26: the owner copied the lab's real files from the rack computer on 2026-11-24 (`reference/lab-2026/`, with a README). They differ from what this system assumed in a few places. Bring the databases, the rack IOC, the plan, the emulation, the GUI and the logger in line with them.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t26`, on branch `emu/t26-lab-files`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never touch the main checkout or another worktree.
- In a new worktree the GUI's sources are missing until you run `git submodule update --init` there (needed before `make -C RAS/mist2 dev-up`).
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo.
- **Shared machine.** The emulation (fixed container names, network 172.30.0.0/24, one volume `mist2emu-save` with the IOCs' saved settings) can exist only once. Take `flock /tmp/mist2emu.lock <command>` for the whole time you have the emulation, the GUI or the logger up, and bring them down before you release the lock. Three other engineers work on this machine at the same time (T23, T24, T25); T23 needs the emulation once. Device cases (`emulation/devtest/run.sh`) need no lock.
- Long commands (the suite takes about 13 minutes, the GUI check about 10, the logger's tests 6) may exceed your tool's time limit: run them in the background, write output and exit code to files, and wait for them.
- Your shell's working directory may reset between commands: start every command with `cd /home/daniel/code/rfq-dip-epics/.claude/worktrees/t26 && ...`.
- Some file tools refuse `.db` files as binary: read them with `cat`, and check every edit with `git diff`.
- Never run `rm` with a shell variable in its path. After a GUI check: `git checkout -- RAS/mist2/tools/screenshots` unless the screenshots changed because of your work (then commit them). Leave no container and no process running when you finish.

# Read first
1. `reference/lab-2026/README.md` and every file beside it: `EPICS/st.cmd`, the four databases, the flow meter sketch, `some_notes.txt`, `rack-serial-devices.txt`.
2. `docs/emulation/STATUS.md`: answer 39 (what the lab's files show), answers 5 and 12, the assumptions A1, A4, A10 to A13, A21, A29, the open points P3, P11, P12, P34.
3. `EPICS/ioc/iocBoot/iocRack/st.cmd`, `ports.sim.cmd`, `ports.real.cmd`, `limits.defaults`; `EPICS/Db/faradaycup.db`, `sensorbox.db`, `matsusada_au20p7.db` (its `DEV` macro), `au_alloff.db`, `supply_first_contact.db`, `mfc.db`, `mfc.proto`, `libcom1_device.db`; `EPICS/README` ("Alarms").
4. `docs/emulation/README.md` section 9 (how a device is added or changed), `plan/controls.yaml` (the devices concerned), `emulation/sim/config/rack.yaml` and `plant.yaml`, `emulation/tests/README.md`.
5. `EPICS/ioc/host/README.md`, `99-mist2-matsusada.rules`, `docs/emulation/LAB-SETUP.md`.

# What the lab's files show (read by the lead; check each yourself)
- **The source supply is `AU-20P15-1`** in the lab (`matsusada_au20p15.db`, unit 1): the same records as the 7.5 mA supplies with 15 mA full scale. This system serves it as `AU-20P7-1` (`matsusada_au20p7.db` with `UNITNUM=1,IFS=15`). The owner's rule is that existing PVs keep their names.
- **The Faraday cup is `FC1`**, an Opta on a USB serial line (115200 8N1), libcom1, two values: `FC1:data`, `FC1:i1:getcurrent`, `FC1:i2:getcurrent`. This system assumed `FC`, one value `FC:current:get`, TCP (A13). What `i1` and `i2` are and their unit is not known.
- **The flow meters are `FLOW`**, a second Opta on a USB serial line (115200 8N1), libcom1, five values `FLOW:f1:getflow` to `f5`. By the sketch's arithmetic (1260 pulses per litre, counted for 0.5 s, factor 0.095238) the unit is litres per minute. Which cooling circuit each is, is not known. The lab's `st.cmd` no longer loads the sensor box; the owner said (answer 5) that the Opta flow readout replaces it.
- **The boards as last flashed speak libcom1 protocol 1** (the Arduino library on the rack computer has no protocol 2): the query `A` works, identity and acknowledged sets do not. The flow meter sketch is protocol 1; the Faraday cup Opta's sketch was not found.
- **The MFC** is loaded in the lab (`MFC:getSP`, `MFC:setSP`, 9600 8N1, address 254 in the protocol file), without the wink records and without a flow read-back.
- **Line settings** of the lab's `st.cmd` agree with `ports.real.cmd` for the gauge controller (115200, even), interlock box, valve box, nAIM, MFC and the Matsusada lines.
- **Serial numbers** (`rack-serial-devices.txt`, joined with the COM numbers of the lab's `st.cmd` and of `some_notes.txt`): COM6 gauge controller, Teensy `16c0:0483`, serial `3596460`; COM11 interlock box, Mega `2341:0042`, serial `954323138373519002A2`; COM12 valve box, Mega, serial `95433343733351502071`; COM13 MFC, FTDI `0403:6001`, serial `FTJRNRWQ`; COM8 TDK (notes of 2022), FTDI, serial `A5051Z0G`. Without a serial number over USB, as Windows saw them: the Matsusada adapters (`1192:1000`, three entries named after USB sockets), the Prolific adapters (COM3 nAIM, COM19 REK), the Arduino Micro of the thermocouples (COM22). The Optas have serial numbers, but the list does not say which belongs to which COM number.
- **Different from the owner's answer 12, and not yours to change:** the lab's `st.cmd` has units 2, 3, 4 on one Matsusada line and 1, 5 on the other, with unit 4 as "Lens 3" and unit 5 as "Lens 2". The owner's answer of 2026-11-21 (1 and 2 on the USB-OPT, 3 and 4 on the CO-U32, unit 4 is lens 2) stands until he says otherwise.

# What to build
R1. **The source supply under the lab's name.** Unit 1 is `AU-20P15-1:...` everywhere: the rack IOC (`DEV=AU-20P15`), its first contact, the all-off record's request, `limits.defaults`, the plan, the registry, the tests, the GUI, the logger, the documents. No alias under the old name: `AU-20P7-1` was this system's assumption, not a PV of the lab. Say what happens to a saved limit of the old name in the emulation's volume and in the suite's check of the saved settings.
R2. **The Faraday cup as the lab has it:** prefix `FC1`, the three record names above, two values. Keep what this system adds to every libcom1 database (the alarm rule of `EPICS/README`, units where known). It must work with the protocol 1 firmware that is on the board: nothing in it may need protocol 2, and no identity records are loaded for it until its firmware is known. The assumed `FC:current:get` goes. In the simulation the plant model drives `i1` (assumed to be the cup current, in A: say so where it is configured); `i2` is a constant.
R3. **The flow meters:** a database from the lab's `IOC.flowmeters.db` with the same record names, the unit l/min with the arithmetic in its header, the alarm rule, protocol 1 as for R2. A simulated device, the plan entry (cooling), the GUI's cooling page with five flows named "Flow 1" to "Flow 5" until the owner names the circuits, the logger's tier as for the flows it replaces.
R4. **The sensor box leaves the rack IOC** (the lab no longer loads it; answer 5): out of `st.cmd`, the port files, the simulator configuration, the GUI and the logger. Its database and its device case stay in the repository. In the plan it is marked as replaced, not deleted.
R5. **A simulated libcom1 device of protocol 1.** If the simulator cannot answer as a protocol 1 board does (`ERR0` to `g`, `S`, `I`, `P`), give it that as an option, checked against `AVR/libcom1/README.md`, and run the Faraday cup and the flow meters on it in the emulation, since that is what the lab's boards are.
R6. **The MFC: compare, change only on proof.** Every PV of the lab's `IOC.mfc.db` is served under its name and type. Compare the protocol strings of the lab's `mfc.proto` with ours (terminator, `;FF`, the reply the lab's comment shows, `@@@000ACK` followed by a number). Report every difference. Change ours only where a test shows that it would not read what the lab's file reads.
R7. **The real port file and the names.** `ports.real.cmd` of the rack IOC: the Faraday cup and the flow meters as serial lines (115200 8N1), the sensor box out. A rule file `EPICS/ioc/host/99-mist2-serial.rules` that gives the names of `ports.real.cmd` to the devices whose serial number is known (list above; the TDK's belongs to the platform computer), each line with its source. For the others the documents say how they are named (`/dev/serial/by-path/`, one device plugged in at a time). In `99-mist2-matsusada.rules` say that the name by serial number works only if the adapter reports one under Linux, which the Windows list does not suggest. Check both rule files with `udevadm verify` in an Ubuntu 24.04 container; they stay marked as not tested on hardware.
R8. **`docs/emulation/LAB-SETUP.md`:** the device table (names, lines, what to read first), the firmware paragraph (protocol 1 on the boards as flashed; the flow meter sketch is in `reference/lab-2026`; the Faraday cup Opta's sketch is not known), the names by serial number. `EPICS/ioc/host/README.md`, `docs/emulation/README.md` and `DESIGN.md` where they name what you changed.
R9. **The plan stays the truth:** devices, PV names, notes; `python plan/build.py` without warnings; registry and `plan/out/` regenerated as a commit of their own. Do not raise the plan's revision (the lead does at the merge).

# Tests
1. `make -C emulation plan-check`.
2. The system suite passes, with the saved settings as the brief's R1 explains. It takes its devices from the registry: say which tests had names written into them and what you changed. Its time is used up (about 13 minutes): removing the sensor box and adding the flow meters must not make it longer; say the time before and after.
3. The device case `faradaycup` for `FC1` with two values on a protocol 1 board, and a device case for the flow meters: valid values, the unit, INVALID when the board is silent and valid again, and that no identity or acknowledged command is sent (read the simulator's log).
4. The simulators' tests (`emulation/sim/run_tests.sh`), with the protocol 1 option.
5. The GUI check (`RAS/mist2/tools/gui-check.sh`) and the logger's tests (`make -C logger test`) pass.
6. By hand, in the emulation with the plant model: the source supply's page and window under its new name, the Faraday cup's two values, the cooling page with five flows. Screenshots in the report's list.
See each new test fail once without the property it checks, and say how.

# Files you own
`EPICS/Db/faradaycup.db`, a new flow meter database, `EPICS/ioc/iocBoot/iocRack/` (all files), `EPICS/Db/au_alloff.db` and `supply_first_contact.db` (comments only), `EPICS/ioc/host/` (the new rule file, comments in the Matsusada rule file, `README.md`), `emulation/sim/config/`, `emulation/sim/mist2sim/devices/libcom1.py` with its tests and README line (R5 only), `emulation/devtest/faradaycup`, a new flow meter case, `emulation/tests` (names only), `plan/controls.yaml` with the regenerated registry and `plan/out/`, `RAS/mist2` (configuration and what the GUI check needs; not the submodule), `logger/` (names and dashboards only), `docs/emulation/LAB-SETUP.md`, `README.md`, `DESIGN.md`.
Not yours: `matsusada_au20p7.db` and the other databases' records, the platform IOC, `docs/emulation/STATUS.md`, `PLAN.md`, the files of T23, T24 and T25 (`scans/`, `daq/`, `EPICS/Db/dipole.db`, the picoammeter's files, their device cases and documents). If you find you need a change there, stop at that point and report it with the reason.

# Acceptance (the lead runs these from your worktree)
    flock /tmp/mist2emu.lock make -C emulation plan-check
    flock /tmp/mist2emu.lock make -C emulation test
    emulation/sim/run_tests.sh
    emulation/devtest/run.sh emulation/devtest/faradaycup          (and your flow meter case)
    flock /tmp/mist2emu.lock bash -c 'make -C emulation up && make -C RAS/mist2 dev-up && RAS/mist2/tools/gui-check.sh; rc=$?; make -C RAS/mist2 dev-down; make -C emulation down; exit $rc'
    flock /tmp/mist2emu.lock make -C logger test
All exit 0.

# Rules
- Do not invent facts. A claim about the lab comes from a file in `reference/lab-2026` or `reference/lab-2023`, with its line; what those files do not say stays a configuration value or a question, and is listed.
- Do not rename any PV the lab's files name. Where this system has a PV the lab does not have, it stays.
- No change of behaviour beyond this task. If something here turns out wrong or cannot be built as described, stop and say so in the report instead of building something else.
- A report that says "done" is not evidence: give the commands you ran, their exit codes and the numbers they printed, and say plainly what you did not do or could not show.

# Final report, with these headings
MODEL, BRANCH, BUILT (R1 to R9), THE MFC (every difference), VERIFIED (commands, exit codes, times, how each new test was seen to fail, the suite's time before and after), DECISIONS (with reasons), ASSUMED, NOT VERIFIED, QUESTIONS FOR THE OWNER, NEEDS THE LEAD (text for STATUS.md, what T23's definition for the emulation must name now), COMMITS.
