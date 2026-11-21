You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T8: the automated test of the whole emulated system. A lead engineer wrote this brief, will run your acceptance test himself, and will merge your branch. Other engineers work in parallel on other files, so stay inside the files you own.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t8`, on branch `emu/t8-system-tests`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never edit, stage or commit anything in `/home/daniel/code/rfq-dip-epics` outside your worktree. Check that `git -C /home/daniel/code/rfq-dip-epics/.claude/worktrees/t8 branch --show-current` prints `emu/t8-system-tests`. If not, stop and report.
- Commit on that branch only. Small commits with clear messages. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo. The images `mist2-ioc:dev` and `mist2-tools:dev` exist (`make -C emulation build` rebuilds them from cache).
- **The emulation uses fixed names and addresses** (Compose project `mist2emu`, network `172.30.0.0/24`), so only one copy can run on this machine. The lead and one other engineer may want to start it too. Before you start it, check that it is not running (`docker ps`), and stop it when you are done with a run (`make -C emulation down`). If you find it running and did not start it, wait a few minutes and check again; if it stays up, say so in your report.

# Read first
1. `docs/emulation/DESIGN.md` (the approved design) and `docs/emulation/STATUS.md` (what is done, assumptions, open points).
2. `emulation/README.md`, `emulation/Makefile`, `emulation/compose.yaml`: how the emulation is built, started and stopped. Two IOC containers (`ioc-rack`, `ioc-hv`), two simulator containers (`sim-rack`, `sim-hv`), and the `tools` container in which tests run.
3. `emulation/sim/README.md`: the simulators and their control interface (`mist2sim.control.ControlClient`: `fault`, `clear`, `get`, `set`, `release`, `stats`). `emulation/sim/config/rack.yaml` and `hv.yaml`: which simulator stands behind which device.
4. The registry: `RAS/mist2/ReactApp/src/registry/registry.json` and the `README.md` next to it. It lists every device with every PV, which PVs are written and which read-back belongs to each, safe test ranges, whether a set is acknowledged, and the simulator behind each device. **Your tests take devices and PV names from the registry.** A PV name written into a test is allowed only where a scenario spans several devices, and then it is looked up by device id and role.
5. The per-device test cases under `emulation/devtest/*/test_*.py`: each device was already tested alone against its simulator. They show how each device behaves under faults and what its tests had to wait for. Your suite tests the SYSTEM: everything running together on two IOCs.

# What "done" means for the project (this is what your suite proves)
1. Both IOCs start without a single database or protocol error.
2. An automated test reads every PV of every device, writes every set point and sees the read-back follow, and confirms that a set that gets no acknowledgement ends in an alarm.
3. Fault injection works: a silent simulator turns the PVs of that device INVALID within seconds, and they recover without restarting the IOC.
4. With five AU high-voltage supplies on two chains, the measured update rate of the monitor PVs is reported and matches the bus arithmetic.

# Files you own
- `emulation/tests/` (new)
- `emulation/Makefile`: only the target `test` and helper targets it needs
- `emulation/README.md`: only a section on running the tests
Nothing else. If a database, a simulator, the registry or a startup file is wrong, do NOT fix it: write a test that shows it, mark it as an expected failure with the reason, and report it. Finding such things is part of the job.

# Deliverables

## 1. `make -C emulation test`
One command. It starts the emulation if it is not running, waits until both IOCs answer, runs the suite in the `tools` container, prints a summary and exits with the suite's exit code. It leaves the emulation running if it found it running, and stops it otherwise. `make -C emulation test ARGS="-k valve"` passes arguments to pytest. The IOC and simulator logs of the run are saved under `emulation/build/` (ignored by git) and are available to the tests, because the tools container cannot call Docker.

## 2. The suite (`emulation/tests/`, pytest)
Generated from the registry wherever possible (parametrised tests), so that a device added to the registry is tested without a new line of test code.
- **Startup**: the logs of both IOCs contain no database, protocol, link or startup error. State the patterns. Every PV in the registry is connected, and is served by the IOC that the registry says (rack or platform).
- **Read**: every PV of every device is read and is not INVALID. Exceptions are allowed only where the registry flags them (a supply that is installed but not polled) or where a record cannot have a value before it is first written, and each exception is asserted explicitly, not skipped: the test states what that PV must show.
- **Write**: every set point is written within its safe test range and its read-back follows within a stated time. This includes the output switches of the supplies, the valves, the gauge enable, the mass flow set point and the turbopump start. Devices are returned to their initial state afterwards.
- **Acknowledgement**: for every set that the registry marks as acknowledged: with the device's simulator silent, a write ends in an alarm on the set record, and after the fault is cleared the device has NOT executed that write. For sets without acknowledgement (the Matsusada supplies), the test proves what the design promises instead: the set-point echo goes INVALID.
- **Faults**, for every simulator in the registry, one at a time: `silent` turns every PV of the devices behind it INVALID within the time the registry or the device's own test allows (state the limit per device class, 5 s unless a device needs longer, and say why), the PVs of ALL OTHER devices on both IOCs stay valid and keep updating meanwhile, and after `clear` everything recovers without restarting an IOC. The same for `close`. `garbage` and `trip` where the simulator supports them. On a bus with several units, also one unit silent while its neighbours keep answering.
- **Across the two IOCs**: opening an interlock door (rack IOC) forces the output of the filament discharge supply off (platform IOC) and of the high-voltage supplies (rack IOC), and closing it does not switch anything back on by itself. "All HV off" switches all five supplies off.
- **Update rate**: for the monitor PVs of the AU supplies on both chains, measure the update rate seen by a Channel Access client and the transaction rate counted by the simulator (`stats`), compute the prediction from the simulator's line settings (baud, bits per character, turnaround) and the polls the databases make, and assert agreement within 10 percent. Write the table to `emulation/build/update-rate.md` and print it. Do the same for the filament heating supply as a second example.
- **Clean end**: whatever a test changes, it restores, also when it fails: no fault left in any simulator, outputs off, valves closed, pumps stopped. A final test asserts this state.
- The suite runs in less than 10 minutes. If one scenario needs longer (a turbopump running up), make the simulator faster through its control interface for that test, or mark the test `slow` and exclude it by default with a stated command to include it.

## 3. A short report file `emulation/tests/README.md`
What each test module proves, in one line each, the time limits used and where they come from, and the list of expected failures with their reasons.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    make -C emulation down          # start from nothing
    make -C emulation test
    make -C emulation test          # a second time: the suite must leave the system as it found it
    docker ps                       # nothing of the emulation left running

Both runs exit 0 (expected failures are listed, not hidden), the second run gives the same result as the first, and the update-rate table is printed. The lead will also break things by hand and expects the suite to notice: a simulator stopped with `docker pause`, a wrong baud rate in a simulator configuration, a PV removed from a database.

# Rules
- A test that cannot fail is worth nothing. For each group of tests, make it fail once on purpose (inject the fault it is meant to catch) and say in your report that it did.
- No sleeping for fixed times where a condition can be awaited. Every wait has a timeout and a message that says what did not happen.
- Do not weaken a check to make it pass. If the system does not do what the design says, that is a finding.
- Leave no container running when you finish.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t8-system-tests @ <commit>
    BUILT: one line per module
    RESULT: numbers of tests passed, expected failures, skipped, and the run time, for both runs
    UPDATE RATE: the table
    FINDINGS: everything the suite found wrong or surprising in databases, simulators, registry or startup files, each with the test that shows it
    PROVEN TO FAIL: per group, the fault you injected and the failure you saw
    DECISIONS: choices the brief left open, each with one reason
    NEEDS THE LEAD: changes outside your files, open questions
