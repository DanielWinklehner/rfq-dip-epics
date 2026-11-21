You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T3: the Matsusada high-voltage supplies. A lead engineer wrote this brief, will run your acceptance test himself, and will merge your branch. Other engineers work in parallel on other files, so stay inside the files you own.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t3`, on branch `emu/t3-matsusada`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. `/home/daniel/code/rfq-dip-epics` itself is the lead's worktree: never edit, stage or commit anything there. Check that `git -C /home/daniel/code/rfq-dip-epics/.claude/worktrees/t3 branch --show-current` prints `emu/t3-matsusada`. If not, stop and report.
- Commit on that branch only. Small commits with clear messages. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo. The images `mist2-ioc:dev` and `mist2-tools:dev` exist already (`make -C emulation build` rebuilds them from cache if needed).

# Read first
1. `docs/emulation/DESIGN.md`: the approved design. Sections 1, 2 ("Bus arithmetic") and 3 are yours.
2. `emulation/sim/README.md`: the simulator core you build on, especially "How to write a new device module" (the multi-unit bus example) and the control interface.
3. `emulation/README.md` and `emulation/devtest/example/`: the harness that runs one simulator, one IOC and your tests together.
4. The lab's files from 2023, which are the baseline for PV names and behaviour: `reference/lab-2023/EPICS/Db/matsusada_au20p7.db`, `matsusada_co_ctrl.proto`, `rek.db`, `rek.proto`, and how they are loaded in `reference/lab-2023/EPICS/st.cmd`. The files of the same name in `EPICS/Db` are OLDER. You replace them.
5. The Matsusada CO series manual, rev 0.4: `https://wiki.jlab.org/ciswiki/images/5/5b/CO_series_REV_0.4.pdf` (68 pages; download it to a temporary directory outside the repository and convert it with `pdftotext -layout` in the `mist2-tools:dev` container). Chapters 5 (programming, `#AL`) and 7 (command reference) are the protocol definition. Do not commit the manual.

# Background
Five Matsusada AU 20 kV supplies sit on two optical chains, each chain behind one USB adapter that appears as a 9600 baud serial port. One more Matsusada supply (REK150-24, filament discharge, 150 V 24 A, soon replaced by a 150 V 55 A unit) sits alone on a third port and speaks the same protocol. The CO protocol returns one value per request, and all supplies of a chain share one line, so every extra poll slows every PV on that chain. Facts already checked in the manual: `MN1` answers `MONI1=FFFH` (12 bit), `CH0?` answers `CH0=FFFFH` (16 bit), `STS` answers `#1 CO RM`, SET COMMANDS GET NO ANSWER, and `#AL` addresses all units for `CH0`, `CH1`, `VCN`, `ICN`, `SW`, `RST`, `REN`, `GTL`, `PL`.

| Unit | Role | Model | Full scale | asyn port |
|---|---|---|---|---|
| 1 | Ion source | AU20P15 | 20 kV, 15 mA | `mat_opt` |
| 2 | Puller | AU20N7.5 (negative) | 20 kV, 7.5 mA | `mat_opt` |
| 3 | Lens 1 | AU20P7.5 | 20 kV, 7.5 mA | `mat_co` |
| 5 | Lens 2 | AU20N7.5 (negative) | 20 kV, 7.5 mA | `mat_co` |
| 4 | Lens 3, installed, NOT polled | AU20P7.5 | 20 kV, 7.5 mA | `mat_co` |
| 1 | Filament discharge | REK150-24 | 150 V, 24 A | `REK` |

# Files you own
- `emulation/sim/mist2sim/devices/matsusada_co.py`, `emulation/sim/tests/test_matsusada_co.py`
- `EPICS/Db/matsusada_au20p7.db`, `EPICS/Db/matsusada_co_ctrl.proto`, `EPICS/Db/rek.db`, `EPICS/Db/rek.proto`, `EPICS/Db/au_alloff.db` (new)
- `emulation/devtest/matsusada/` (your test case or cases)
Nothing else. No `st.cmd`, no port files, no Compose file, no other database, nothing in the simulator core. If the core lacks something you need, say so in your report and work around it inside your module.

# Deliverable 1: bus simulator `matsusada_co`
- One simulator is one chain: several units, each with address, full-scale voltage, full-scale current, polarity and a load resistance, all from the configuration file.
- It implements the command set of the manual: unit addressing, `#AL`, case and spacing rules, CR and LF as input delimiter, CR after every reply, wrong commands ignored without a reply, value formats and ranges including the documented out-of-range cases. Where the manual leaves behaviour open, make it a setting with a comment and list it in your report. Known open points: whether queries are answered before `REN` was sent, whether `ICN` and `CH1` are one setting, and the unsolicited `!` that the manual describes for supplies with the output off (setting, default off).
- Plausible behaviour: the output voltage follows the set point with a time constant when the output is on and falls to zero when it is off, the current follows from the load resistance, the current limit holds (constant-current mode pulls the voltage down), the monitors carry a little noise and are quantised to 12 bit.
- Fault `trip`: the supply cuts off as after an overload, the output stays off until `RST`, and the status shows it.
- Each unit exposes its signals (set points, output voltage, output current, output state) on the control interface, so that a plant model can read and drive them later.
- Unit tests without an IOC in `test_matsusada_co.py`.

# Deliverable 2: databases and protocol files
Start from the 2023 lab files. **Keep every PV name and its meaning exactly**: `AU-20P7-$(UNITNUM):voltage:setpoint`, `:voltage:get` (set-point echo), `:voltage:read` (monitor), `:current:setpoint`, `:current:get`, `:current:read`, `:SetToggleOutput`, `:OutputIntlk`, `:ToggleOutput`, `:status:read`, `:read_output_status`, `:power:read`, and the same with prefix `REK-$(UNITNUM)`. Then rework:
1. **Polling.** Only the monitors (`MN1`, `MN2`) are polled fast (macro, default `.1 second`). The set-point echoes are read after each set and every few seconds (macro, default `5 second`). Status is read once a second. Decide what to do with `read_output_status` (`SW?`), which duplicates part of `STS`, so that both PVs stay correct at the lowest bus cost, and say what you chose.
2. **`PRIO = HIGH` on every record that sends a command**, so that a set overtakes queued polls. Show by measurement that it does (time from `caput` to the arrival of the command at the simulator, while the chain is polled).
3. **Macros for full scale and sign**: `VFS`, `IFS` and `POL`. EPICS macros cannot do arithmetic. One way that needs none: `ESLO` holds the constant `1/65535` (or `1/4095` for the monitors) and `ASLO` holds `$(POL)$(VFS)`. `POL` defaults to positive for every supply, which is today's behaviour. Say in your report what else would have to change (drive limits) to show the negative supplies with a minus sign. Defaults must reproduce today's numbers for a 20 kV 7.5 mA unit. Fix the unit label of the REK current read-backs (they say mA, the values are in A).
4. **No acknowledgement exists**, so a set that the supply does not execute cannot raise an "ack missing" alarm. Instead: each set triggers a read of its echo, a supply that does not answer turns its records INVALID, and a set whose echo differs from what was sent is visible as an alarm. Choose the simplest mechanism that does this without new PV names, or with as few new names as possible, and report them.
5. **Output switching.** Keep the lab's chain: `SetToggleOutput` (the operator's request), `OutputIntlk` (forces off while the interlock is open), `ToggleOutput` (sends `ICN`, `RST`, `SW`). Changes:
   - The permit PV becomes a macro `PERMIT` (the lab uses `interlock_open`, non-zero means open). An INVALID or disconnected permit counts as open.
   - After an IOC restart with a supply's output ON, the PVs must show it ON and it must STAY ON. Today `SetToggleOutput` starts at 0 regardless of the supply.
   - Note and report, but do not change: the lab's `toggle_output` sends `ICN 100` on enable, which sets the current limit to 100 % whatever `current:setpoint` says. Make the percentage a macro with default 100, and make the test document the behaviour.
6. **Lens 3 is loaded but not polled**: all scanning switched off by macros for that instance, without a flood of alarms and without bus traffic. Say what its PVs show in that state.
7. **One "all off" PV**: `AU:alloff:set` sends `#AL SW0` on both chains at once, with high priority. Afterwards every supply's request PV and read-backs must agree with reality (off), and switching one supply on again must work with a single write.
8. **A silent supply must not stall its chain.** With the default StreamDevice reply timeout, every poll of a dead unit blocks the line for a second. Choose timeouts so that the healthy supplies on the chain keep a useful update rate, and report the measured rate of a healthy supply while its neighbour is silent.

# Deliverable 3: update-rate report
With five supplies configured as in the table (two chains in one test case, lens 3 loaded but not polled), measure the update rate of the monitor PVs and compare it with the bus arithmetic for the simulator's settings (baud 9600, turnaround from the configuration). Use the simulator's `stats` for the transaction counts and Channel Access for what a client sees. Print a small table: predicted and measured rate per supply, for the turnaround in the configuration and for 16 ms. Also give the rate with lens 3 polled, to show what it costs. Explain any difference above 10 percent.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    emulation/sim/run_tests.sh
    emulation/devtest/run.sh emulation/devtest/matsusada

Both exit 0. The second covers, against the simulator and a real IOC:
- every PV of every supply is read and none is INVALID in normal operation (state the expected state of lens 3);
- every set point is written and its echo and its monitor follow;
- output on and off, the permit forcing it off, `trip` and recovery with a new enable;
- one unit `silent`: its PVs are INVALID within 5 s, the other unit on the chain keeps updating, and after `clear` everything recovers WITHOUT an IOC restart;
- the chain `close`d and reopened: the same;
- `AU:alloff:set`;
- IOC restart with an output on (the harness or your test may restart the IOC process; if the harness cannot do that, say so and show it another way);
- the REK with 24 A and with 55 A full scale;
- the IOC log contains no database, protocol or link error;
- the rate report is printed.

# Rules
- Do not invent protocol details. The manual decides. What it does not say becomes a setting with a comment and a line in your report.
- Keep it small and readable.
- Leave no container running when you finish.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t3-matsusada @ <commit>
    BUILT: one line per deliverable
    PVS: every PV per supply with type and scan, new names marked NEW
    MACROS: every macro of each database with default and meaning, and the dbLoadRecords lines for the six supplies in the table plus au_alloff.db
    SIMULATOR SETTINGS: the configuration keys of matsusada_co, with an example for the two chains and the REK
    VERIFIED: both acceptance commands with exit code and key output, and the rate table
    DECISIONS: choices the brief left open, each with one reason
    ASSUMED: everything the manual did not settle
    NEEDS THE LEAD: changes outside your files, open questions, anything that did not work
