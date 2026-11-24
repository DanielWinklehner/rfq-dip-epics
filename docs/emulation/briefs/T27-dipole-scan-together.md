You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T27: the three parts of the dipole scan were built and tested apart (T23 the scan program, T24 the magnet supply through the DAQ service, T25 the picoammeter). Prove them together: one device case in which the shipped scan program runs the dipole scan against the DAQ service and the picoammeter simulator through one IOC. No hardware is available.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t27`, on branch `emu/t27-dipole-scan-together`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never touch the main checkout or another worktree.
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo. Python tooling runs in the image `mist2-tools:dev`, the IOC in `mist2-ioc:dev`.
- A device case (`emulation/devtest/run.sh <case>`) is its own Compose project on its own network and needs no lock. You do not need the full emulation. Another engineer (T26) works on this machine at the same time, in its own worktree.
- Long commands may exceed your tool's time limit: run anything that takes longer than a minute in the background, write output and exit code to files, and look at the files in short steps.
- Your shell's working directory may reset between commands: start every command with `cd /home/daniel/code/rfq-dip-epics/.claude/worktrees/t27 && ...`.
- Some file tools refuse `.db` files as binary: read them with `cat`, and check every edit with `git diff`.
- Never run `rm` with a shell variable in its path. Leave no container and no process running when you finish.

# Read first
1. `docs/emulation/SCAN.md`, `DAQ.md`, `PICOAMMETER.md`, and `docs/emulation/STATUS.md`: the block "The dipole scan, first stage" under "Done", assumptions A44 to A46, open points P55 to P57.
2. `scans/config/dipole.yaml`, `scans/README.md`; `daq/config/dipole.yaml`, `daq/README.md`; the headers of `EPICS/Db/dipole.db`, `picoammeter.db`, `keithley6485.proto`.
3. The three device cases `emulation/devtest/scan`, `dipole` (its `sim.cmd` and `run_service.sh`: how a case runs the service and stops and starts it) and `picoammeter`; `emulation/devtest/run.sh` (header) and `compose.yaml`.
4. `emulation/sim/README.md`: the control port of a simulator (how a value of the picoammeter simulator is set from outside).

# What to build
R1. **A device case `emulation/devtest/dipolescan`.** Its "simulator" side runs three things: the DAQ service with the `sim` backend, the picoammeter simulator, and a small coupling program of the case that reads the magnet current from the service's status port and sets the picoammeter's current through the simulator's control port. The IOC loads `dipole.db` and `picoammeter.db` with the loads their headers name (`libcom1_device.db`, `first_contact.db`).
R2. **The coupling is a model of the case, not of the machine:** a spectrum of three peaks over the magnet current on a small background, the positions in the ratio of the square roots of 1, 2 and 3 (as three ion species of mass 1, 2, 3 would arrive at the same energy), heights and widths of your choice, all in one configuration file with the remark that no number is measured on MIST-2.
R3. **The scan runs as it will run for the owner:** `python -m mist2scan run` with `scans/config/dipole.yaml`. Use the command line's overrides for range, step and dwell so that the case stays short; anything else that has to differ from the shipped definition is a finding for your report, not a second definition.
R4. **Say what the numbers of the three parts mean together,** measured: the picoammeter delivers one value per second and the dwell of the shipped definition is one second. How many values does a point get, what does the scan take per point, and which dwell, poll period and integration time would you set for a scan of 100 points? Say what the shipped definition and the databases' defaults should be, with the reason. Change a default only inside the files you own; anything else is a recommendation.
R5. **A section in `docs/emulation/SCAN.md`:** the dipole scan in the emulation: how to run the case, what an operator must do before a scan (R6, test 1), the table of R4.

# Tests
1. **After power-on the scan refuses.** The picoammeter's zero check is on after power-on, so `pico1:current:get` is INVALID: `check` and `run` refuse, name the reason, and write nothing to the magnet. With zero check switched off through its PV the scan starts.
2. **The spectrum.** A scan across the three peaks: found where the coupling puts them, within one step; the read-back means within the tolerance; the peak heights within the picoammeter's noise of the model.
3. **Overflow at a peak.** With a fixed range below the highest peak, the points on that peak are missing with their reason, the others are measured, and the scan completes.
4. **The service stops in the middle** (the case can stop and start it): a clean end, nothing written after it, the file says why and where the magnet was left. After the service is started again its held value is "not known": say what `check` and `run` do then, and whether that is what an operator needs.
5. **The picoammeter goes silent in the middle:** the end the definition asks for (a required detector lost), the magnet taken back in part steps.
6. **An IOC restart in the middle:** a clean end, no write after it, the magnet current unchanged at the service (read it from the service, not from the IOC).
7. The three existing cases and the unit tests of `scans` and `daq` still pass.
See each of tests 1 to 6 fail once without the property it checks, and say how.

# If a part does not do what its document says
You may correct `scans/mist2scan`, `daq/mist2daq`, `EPICS/Db/dipole.db`, `EPICS/Db/picoammeter.db`, `keithley6485.proto` and the picoammeter's simulator, each time with a test that fails before the correction (in the part's own tests or case) and a line in its document. Every such correction goes into your report with the reason. A change of what a part is meant to do (for example what the scan does after a lost actuator) is not a correction: report it as a question.

# Files you own
`emulation/devtest/dipolescan/**`, the new section of `docs/emulation/SCAN.md`, and the corrections named above. Not yours: `plan/controls.yaml`, the registry, `EPICS/Db/libcom1.proto`, `first_contact.db`, `libcom1_device.db`, the other databases, the simulator's core, the IOCs, `emulation/tests`, `docs/emulation/STATUS.md`, `PLAN.md`, `README.md`, `LAB-SETUP.md`. If you find you need a change there, stop at that point and report it with the reason.

# Acceptance (the lead runs these from your worktree)
    emulation/devtest/run.sh emulation/devtest/dipolescan
    emulation/devtest/run.sh emulation/devtest/scan
    emulation/devtest/run.sh emulation/devtest/dipole
    emulation/devtest/run.sh emulation/devtest/picoammeter
    emulation/sim/run_tests.sh
    the unit tests of scans and daq (the docker commands of SCAN.md and DAQ.md)
    make -C emulation plan-check
All exit 0.

# Rules
- Do not invent facts about the machine: every number of the coupling and of the definitions is a property of the case or marked ASSUMED.
- No change of behaviour beyond this task. If something here turns out wrong or cannot be built as described, stop and say so in the report instead of building something else.
- A report that says "done" is not evidence: give the commands you ran, their exit codes and the numbers they printed, and say plainly what you did not do or could not show.

# Final report, with these headings
MODEL, BRANCH, BUILT, THE NUMBERS TOGETHER (R4, with the table), VERIFIED (commands, exit codes, times, how each test was seen to fail), CORRECTIONS TO THE PARTS (each with its failing test), DECISIONS (with reasons), ASSUMED, NOT VERIFIED, QUESTIONS FOR THE OWNER, NEEDS THE LEAD (text for STATUS.md and for the plan), COMMITS.
