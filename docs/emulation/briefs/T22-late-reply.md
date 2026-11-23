You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T22: after one late reply on the serial line of the Matsusada or REK high-voltage supplies, the requests and replies of that line must be in step again at once, and a reading that carries a state or a setting must never take another supply's reply as its own (open point P49). A lead engineer wrote this brief, will run your acceptance tests himself, and will merge your branch.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t22`, on branch `emu/t22-late-reply`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never edit, stage or commit anything in `/home/daniel/code/rfq-dip-epics` outside your worktree.
- In a new worktree the GUI's sources are missing until you run `git submodule update --init` there (needed before `make -C RAS/mist2 dev-up`).
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo.
- **Shared machine.** The emulation (fixed container names, network 172.30.0.0/24, one volume `mist2emu-save` with the IOCs' saved settings) can exist only once. Take the lock for the whole time you have the emulation or a device case up, and bring down what you started before you release it: `flock /tmp/mist2emu.lock bash -c '<start>; <work>; <stop>'`, or a `make` target that starts and stops by itself under `flock /tmp/mist2emu.lock`. Never leave anything running outside the lock, and never stop containers you did not start. If the lock is taken, wait.
- Leave the saved settings as you found them (the suite prints at its start what differs from `limits.defaults`).
- Long commands (the suite takes about 12.8 minutes, the GUI check about 10, the device case 10) may exceed your tool's time limit: run them in the background, write output and exit code to files, and wait for them.
- Your shell's working directory may reset between commands: start every command with `cd /home/daniel/code/rfq-dip-epics/.claude/worktrees/t22 && ...`.
- Some file tools refuse `.db` files as binary: read them with `cat`, and check every edit with `git diff`.
- Never run `rm` with a shell variable in its path.
- After a GUI check: `git checkout -- RAS/mist2/tools/screenshots` (it rewrites screenshots).
- Leave no container and no process running when you finish.

# Read first
1. `docs/emulation/STATUS.md`: open point P49 (this task), P50, P32, and assumption A24.
2. `EPICS/Db/matsusada_co_ctrl.proto` with its header; `EPICS/Db/rek.proto` is the same file apart from its header, and the two are kept in step.
3. `EPICS/Db/matsusada_au20p7.db`: the header, the monitor cycle (`voltage:read`, `current:read`, `power:read`, the `_poll` records), `voltage:get`, `current:get`, `read_output_status`, `status:read`, `_init:probe`, `output:init`, `ToggleOutput`, `_limit:apply`. `EPICS/Db/rek.db` has the same records. `EPICS/Db/supply_first_contact.db` with its header: what the first contact copies from the probe's answer (the request `SetToggleOutput`, `ToggleOutput`, the gate's previous value) and from `voltage:get` (the voltage set point).
4. The device case `emulation/devtest/matsusada`: `ioc.cmd`, `sim.yaml`, `mat.py`, `test_matsusada.py`, `test_rates.py` (with `build/rate_report.txt` after a run), `test_permit_enforce.py` (its trace of what the IOC writes to the line), `test_switch_resend.py` (how it pauses a unit's periodic reads, how it sets a simulator fault).
5. The simulator: `emulation/sim/mist2sim/devices/matsusada_co.py` and `emulation/sim/mist2sim/core/simulator.py`: `_worker` (one transaction at a time, each held back by the transmission time of its characters), `add_fault` (`slow` with `ms`, and `duration`).
6. `EPICS/ioc/host/matsusada_probe.py`: a read-only probe for the real hardware that lists the replies the protocol file expects.

# The fault
Seen once, in a full run of the device case (2026-11-23). All four simulated lines gave "No reply within 150 ms" at the same moment (a pause of the machine). After that:

    14:44:35.896859 mat_co AU-20P7-4:current:read: No reply within 150 ms to "#4 MN2<0d>"
    14:44:36.019076 mat_co AU-20P7-3:voltage:read: Input "MONI2=000H"
    14:44:36.019098 mat_co AU-20P7-3:voltage:read: got "2=000H" where "1=" was expected
    14:44:36.066682 mat_co AU-20P7-3:current:read: Input "MONI1=001H"
    ... one mismatch every 24 ms ...

The reply to `#4 MN2` came after the reply timeout (150 ms) and the 50 ms the protocol waits after it, so it was taken as the reply to the next request, `#3 MN1`. From then on every request was paired with the reply to the one before it. The two lines with one polled supply were in step again after 0.2 s (5 mismatches each). The two lines with two polled supplies stayed out of step for 15 s and 30 s. Mismatches logged in that time on the line of AU-20P7-1 and -2: about 260 per monitor record of unit 1, about 31 per monitor record of unit 2. My reading, which you confirm or correct: the requests of the two supplies alternate on the line (1 MN1, 2 MN1, 1 MN2, 2 MN2), so one supply gets the other's reply of the same kind and accepts it without alarm, and the other gets a reply of the wrong kind and mismatches. The replies to MN1, MN2, CH0?, CH1? and SW? carry no unit number; only the reply to STS does (`#<unit> CO RM`).

Read by me in the StreamDevice and the databases of our image (`docker run --rm --entrypoint sh mist2-ioc:dev -c '...'`, StreamDevice under `/opt/epics/support/StreamDevice/src`, base under `/opt/epics/base/modules/database/src`); check each yourself and name the lines:
- `AsynDriverInterface.cc`, `writeHandler`: before every write, input that has already arrived is read with timeout 0 and discarded. So a late reply does harm only when it arrives after the next request has been written.
- `StreamCore.cc`, `finishProtocol`: a mismatch (`ScanError`) ends the protocol at once unless an `@mismatch` handler is defined; a handler's commands run before the line is released (`busUnlock` comes after), and the record still gets the original error (`runningHandler`). `StreamEpics.cc`, `protocolFinishHook`: `ScanError` gives CALC alarm, `ReplyTimeout` gives TIMEOUT.
- `StreamEpics.cc`, `protocolFinishHook`: the record completes in a callback (`callbackRequest`), not in the port's thread. So the request of a record that is processed by a forward link (`current:read` after `voltage:read`) is queued after the port's thread has already taken the next waiting request. That would explain the alternation.
- The monitor cycle keeps a line with two polled supplies full (2 x 48 ms per 100 ms tick, plus the status and echo reads). With no idle time on the line, nothing discards the stray reply, and the state lasts until something else breaks it.
- Why it matters most at the first contact: `_init:probe` (REN, SW?) of all supplies of a line are processed one after the other at the IOC start. If the SW reply of one supply is late, the next supply's probe takes it, and `supply_first_contact.db` copies that state into the next supply's request, its `ToggleOutput` and its gate. `voltage:get` (CH0?) is read the same way, and its value becomes the voltage set point the IOC shows.

# What to build
R1. **Back in step after one mismatch.** An `@mismatch` handler in both protocol files that keeps the line for as long as the outstanding reply needs to arrive (the file's header gives the times: reply 17 to 19 ms, turnaround 5 to 16 ms), so that the next write discards it. The existing `@replytimeout { wait 50; }` stays. Argue the wait from those numbers and from the source lines, in the file's comment. It also covers a line that nobody asked for (the manual's "!" of a unit that goes off).
R2. **A reply without a unit number is not trusted where it carries a state or a setting.** Every protocol whose reply is copied or compared as a state or a setting first asks the same unit for its status and checks the unit number in the reply, in the same protocol, before its own query: `probe`, `get_output_status`, `get_voltage`, `get_current`, and the read-backs of `toggle_output`, `set_voltage` and `set_current`. The check discards the status itself (`%*{...}` if StreamDevice 2.8.26 accepts the skip flag with an enum: verify it in `StreamCore.cc` and in a test; if not, say what you used instead). The order within a protocol is yours to argue. Why this closes it: a stray reply is older than every reply to a later request, so it is always the first input a protocol reads after it; the first `in` of these protocols is then the status check, which a stray fails unless it is this unit's own status. Say what happens in that last case.
R3. **The monitors stay as they are** (`read_voltage`, `read_current`): one request, one reply. They are read ten times a second and the line is full; a status request in front of each would cost nearly half the update rate. That is the owner's decision, not ours (see R6). With R1 a monitor can take a neighbour's reply for at most one cycle before the first mismatch puts the line in step.
R4. **Line time kept.** A supply that does not answer costs what it costs today (150 ms + 50 ms per request, the first `in` of every protocol). `test_rates.py` passes unchanged. Say what R2 adds per unit and per second in normal operation, measured.
R5. **Both protocol files in step,** headers and comments brought up to date (what is sent at the first contact, the line times, the argument of the header about the `LockTimeout`). Comments in `matsusada_au20p7.db`, `rek.db` and `supply_first_contact.db` that name what a protocol sends are brought up to date; no record changes. `EPICS/ioc/host/matsusada_probe.py`: bring its table in step if it lists what these protocols expect, and say that it is not tested (no hardware).
R6. **Report, do not change** (I decide with the owner), measured:
   a. the monitors after one late reply, with R1 in place: how many values of a neighbour a monitor record accepted, and for how long it showed them, on a line of two polled supplies (and of three, if the case's unit 6 can be polled for it at little cost);
   b. the update rate of the monitors per supply today (one and two polled supplies on a line), and what it would be if the monitors were checked as in R2 (an experiment on a copy of the protocol file, not committed);
   c. a supply whose every reply is late (the `slow` fault left on, 300 ms): what the other supply's records show, with R1 and R2;
   d. anything a stray reply can still do that this brief does not name.
R7. **The plan stays the truth.** No record is added. If a note in `plan/controls.yaml` no longer says what happens, bring it up to date; `python plan/build.py` without warnings; do not raise the plan's revision; regenerated files as a commit of their own.

Unknown and to stay unknown here: whether the real supplies answer queries under local control (A24), and whether the STS reply of the real supply is exactly what the manual prints. `read_status` builds on that format today; R2 makes every state read build on it. I record that as an assumption; do not build anything around it.

# Tests
All in the device case `emulation/devtest/matsusada`; the system suite gets no new test (its time budget is used up, P32) and must pass unchanged.

One late reply, made on purpose: the `slow` fault with `ms` and a short `duration` holds the simulated line for one reply and has expired when the next request is processed. Check that this gives exactly one late reply, and say how you know. If the simulator cannot do what a test needs, a small addition to the fault modes in `emulation/sim/mist2sim/core/simulator.py` is allowed, with a unit test in `emulation/sim/tests` and a line in your report.

1. **The fault as it is,** before your change (keep the test, it must fail without R1): two supplies on one line, both on, at clearly different voltages; one reply of one of them 300 ms late. Print the timeline: what each monitor record showed, with alarm state and time, for 10 s. I expect one supply showing the other's voltage for seconds without alarm. Say what you saw.
2. **With R1:** the same. The line is in step after the first mismatch; no monitor shows a neighbour's value after that; say how many it accepted before (R6a). Repeat it often enough to cover the phase of the late reply within the cycle (say how many and why), and for a late reply of each kind (MN1, MN2, STS, SW?, CH0?, CH1?).
3. **R2, each protocol:** with the periodic reads paused so that the order on the line is yours, supply A's reply late and supply B's request of the same kind next on the line, A and B in opposite states (or with different settings): B's record never shows A's value; it is INVALID or shows its own. For `get_output_status`, `get_voltage`, `get_current`, the read-back of `toggle_output` (a switching of B that the supply did not execute must not be confirmed by A's reply), and the read-backs of the two set points. Each seen to fail before the change.
4. **The first contact:** an IOC start with one supply of a line on and the other off, and with different voltage settings, the first one's replies late. The other supply takes over its own state and its own setting: request, `ToggleOutput`, the gate, the voltage set point. Both directions (on/off and off/on). Seen to fail before the change. The test must not depend on how soon its Channel Access client finds the restarted IOC.
5. **A line nobody asked for** (the simulator's `bang_when_off`, or whatever the simulator offers): one mismatch, then in step. If the simulator cannot send one without a change, say so and leave it out.
6. **R4:** a silent supply beside a polled one: the rate of the polled one as in `test_rates.py` today.
7. The existing tests of the device case pass. If one counted or compared what the IOC writes to the line and now sees the status requests, say which, and change it only as far as needed.

See every new test fail once without the change, and say how. Print timelines where a test is about an order of events, so that I can read them in the log.

Lessons of the last tasks that apply here:
- A test must not depend on how soon its Channel Access client finds a restarted IOC (it can take longer than `GRACE`).
- The device case itself can be hit by a stall of the machine (that is how this fault was found). A test that waits for "in step" should say so in its failure message, with the line's last mismatches.

# Files you own
- `EPICS/Db/matsusada_co_ctrl.proto`, `EPICS/Db/rek.proto`
- comments only in `EPICS/Db/matsusada_au20p7.db`, `EPICS/Db/rek.db`, `EPICS/Db/supply_first_contact.db`
- `EPICS/ioc/host/matsusada_probe.py` (its table only)
- `emulation/devtest/matsusada` (tests, `mat.py`, `ioc.cmd`, `sim.yaml`)
- `emulation/sim/mist2sim/core/simulator.py` and `emulation/sim/tests` only for a fault mode a test needs
- `emulation/tests/` only where an existing test must know the status requests
- `plan/controls.yaml` (notes only), the regenerated registry and `plan/out/`
Not yours: the records of the databases, the IOCs' `st.cmd`, the device models under `emulation/sim/mist2sim/devices`, `RAS/` except the generated registry, `logger/`, `loops/`, `docs/emulation/STATUS.md`, `PLAN.md`, `README.md`, `DESIGN.md`.

# Acceptance (the lead runs these from your worktree)
    flock /tmp/mist2emu.lock make -C emulation plan-check
    flock /tmp/mist2emu.lock make -C emulation test
    flock /tmp/mist2emu.lock emulation/devtest/run.sh emulation/devtest/matsusada
    flock /tmp/mist2emu.lock bash -c 'make -C emulation up && make -C RAS/mist2 dev-up && RAS/mist2/tools/gui-check.sh; rc=$?; make -C RAS/mist2 dev-down; make -C emulation down; exit $rc'
All exit 0, the suite with the saved settings unchanged. The lead then puts the old protocol files back himself, runs tests 1, 3 and 4 and reads their timelines, and runs them again with yours.

# Rules
- Do not invent facts. A claim about how StreamDevice or EPICS behaves comes with the file and line of the source in our image. A claim about the real supply comes from the manual named in the protocol file's header, or is marked as assumed.
- No change of behaviour beyond this task. If something here turns out wrong or cannot be built as described, stop and say so in the report instead of building something else.
- A report that says "done" is not evidence: give the commands you ran, their exit codes and the numbers they printed, and say plainly what you did not do or could not show.

# Final report, with these headings
MODEL, BRANCH, BUILT, HOW IT WORKS (step by step with the source lines), R6 (a, b, c, d, with the numbers), VERIFIED (commands, exit codes, times, the timelines of tests 1 to 4 without and with the change, and how each new test was seen to fail), DECISIONS, ASSUMED, NEEDS THE LEAD (text for STATUS.md, anything of the plan the lead must do).
