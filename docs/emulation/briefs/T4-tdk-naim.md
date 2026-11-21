You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T4: the TDK-Lambda filament heating supply and the Edwards nAIM ion gauge. A lead engineer wrote this brief, will run your acceptance test himself, and will merge your branch. Other engineers work in parallel on other files, so stay inside the files you own.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t4`, on branch `emu/t4-tdk-naim`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. `/home/daniel/code/rfq-dip-epics` itself is the lead's worktree: never edit, stage or commit anything there. Check that `git -C /home/daniel/code/rfq-dip-epics/.claude/worktrees/t4 branch --show-current` prints `emu/t4-tdk-naim`. If not, stop and report.
- Commit on that branch only. Small commits with clear messages. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Docker works without sudo. The images `mist2-ioc:dev` and `mist2-tools:dev` exist already (`make -C emulation build` rebuilds them from cache if needed).

# Read first
1. `docs/emulation/DESIGN.md`: the approved design, sections 1 to 3.
2. `emulation/sim/README.md`: the simulator core you build on, especially "How to write a new device module" and the control interface.
3. `emulation/README.md` and `emulation/devtest/example/`: the harness that runs one simulator, one IOC and your tests together.
4. The lab's files from 2023, the baseline for PV names and behaviour: `reference/lab-2023/EPICS/Db/tdk.db`, `tdk.proto`, `IOC.aim.db`, `aim.proto`, and how they are loaded in `reference/lab-2023/EPICS/st.cmd`. The files `tdk.db`, `tdk.proto`, `aim.db`, `aim.proto` in `EPICS/Db` are OLDER and use other PV names. You replace them.
5. Manuals (download to a temporary directory outside the repository, convert with `pdftotext -layout` in the `mist2-tools:dev` container, do not commit them):
   - TDK-Lambda GENESYS GEN 2.4 kW user manual, which covers the GEN 8-300: `https://heliosps.com/wp-content/uploads/2017/06/GEN-2-4KW-Manual.pdf`. Chapter 7 is the RS-232/RS-485 remote control: addressing (`ADR n`), acknowledgement (`OK`), error messages (`E01`..., `C01`...), optional checksum, command set, fault and status registers.
   - Edwards serial protocol family (queries `?V<object>`, commands `!C<object>`, replies `=V...` and `*C...`, all ending in CR): `https://www.lesker.com/newweb/Gauges/pdf/tic-instrument-controller-serial-communications.pdf`. That is the manual of the TIC controller, NOT of the nAIM gauge. It shows the message structure and the error replies. The instruction manual of the nAIM itself (RS-232 version, part numbers D1469xxxx) I could not find. Search for it. If you cannot find it either, say so, and build on what the lab's protocol file shows works: `?V752` answered by `=V752 <pressure>;<number>`, and `!C752 0` / `!C752 1`.

# Background
The TDK-Lambda GENESYS 8-300 (8 V, 300 A) heats the filament of the ion source. It sits on the high-voltage platform and is polled at 10 Hz today. It will later be the actuator of a control loop for the discharge current, so its simulator must behave plausibly in time. The Edwards nAIM is a cold-cathode ion gauge with its own RS-232 interface in the rack.

# Files you own
- `emulation/sim/mist2sim/devices/tdk_genesys.py`, `emulation/sim/mist2sim/devices/edwards_naim.py`, and one unit test file for each under `emulation/sim/tests/`
- `EPICS/Db/tdk.db`, `EPICS/Db/tdk.proto`, `EPICS/Db/aim.db`, `EPICS/Db/aim.proto`
- `emulation/devtest/tdk/` and `emulation/devtest/naim/`
Nothing else. No `st.cmd`, no port files, no Compose file, nothing in the simulator core. If the core lacks something you need, say so in your report and work around it inside your module.

# Deliverable 1: TDK
**Database and protocol**, starting from the 2023 lab files. **Keep every PV name and its meaning exactly**: `$(DEVICE):voltage:setpoint`, `:voltage:read`, `:current:setpoint`, `:current:read`, `:status:setpoint`, `:status:get` (the lab loads it with `DEVICE=TDK`). Then:
- Add three records that the project plan asks for: `$(DEVICE):power:get` (measured voltage times measured current, in W), `$(DEVICE):mode:get` (off, constant voltage, constant current, from `MODE?`) and `$(DEVICE):fault:get` (the fault register from `FLT?`, with an alarm when a fault bit is set). No other new PV names.
- Units, precision, drive limits and descriptions on every record. Voltage and current limits of the supply are macros with the 8 V, 300 A defaults.
- Every set is acknowledged by the supply with `OK`. A set that is answered with an error message, or not at all, must end in an alarm on the set record. Check that this holds for all three set records.
- Polling: the two measurements fast (macro, default `.1 second`), output state, mode and fault register once a second.
- The address (`ADR 6` today) becomes a macro with default 6.
- **Recovery.** A GENESYS that was switched off and on has forgotten that it was addressed and does not answer until it gets `ADR` again. On a serial line the IOC does not see that as a reconnect. The PVs must recover by themselves within 15 s after the supply comes back, without an IOC restart and on a connection that never dropped. Check in the manual how an unaddressed supply behaves and build the simplest mechanism that covers it.

**Simulator `tdk_genesys`**: the command set of chapter 7 as far as the database uses it plus what a person would type to check it by hand (identity, set-point queries, `MODE?`, `FLT?`, status and fault registers as documented, the error messages, the optional checksum). Behaviour: constant-voltage and constant-current operation into a load resistance from the configuration (a hot filament is a few tens of milliohms), voltage and current following their set points with a time constant, a little noise on the measurements. `trip` is a fault shutdown as the manual describes it (output off, fault bit set, the documented way to clear it). A separate control-interface action or setting simulates the power cycle described above. Signals for a later plant model: programmed and measured voltage and current, output state.

# Deliverable 2: nAIM
**Database and protocol**, starting from the 2023 lab files. **Keep the PV names**: `$(DEVICE):getpressure` and `$(DEVICE):enable` (the lab loads them with `DEVICE=AIM`). Then:
- The lab's `enable` sends the command and does not read the reply. Read the reply, so that a rejected or unanswered command ends in an alarm.
- The second number in the pressure reply is ignored today. Find out what it is. If it is a gauge state or an alert code, use it to set the alarm severity of `getpressure` (for example gauge off, not struck, error), WITHOUT adding PV names. If you cannot find out, leave it ignored and report that.
- Unit and precision on `getpressure`. The lab's database says torr. If the manual says the gauge reports another unit, do not convert silently: report it.
- Sensible polling rate (the lab polls at 10 Hz, which a cold-cathode gauge does not need: propose a rate, as a macro).

**Simulator `edwards_naim`**: the message format of the Edwards protocol with its error replies, object 752 as far as you can establish it, pressure as a signal that a plant model can drive (a plausible standalone default: a slowly drifting value around 1e-6), gauge on and off, and what the gauge reports while it is off. Everything you could not establish from a document is a setting, listed in your report.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    emulation/sim/run_tests.sh
    emulation/devtest/run.sh emulation/devtest/tdk
    emulation/devtest/run.sh emulation/devtest/naim

All exit 0. Against the simulator and a real IOC the cases cover:
- every PV is read and none is INVALID in normal operation;
- every set point is written and its read-back follows (for the TDK in constant-voltage AND in constant-current operation, and the output switch);
- a set that gets an error reply ends in an alarm, and a set that gets no reply ends in an alarm (TDK: all three set records; nAIM: `enable`);
- `silent`: the PVs are INVALID within 5 s and recover after `clear` without an IOC restart; `close` and reopen: the same; `garbage`: alarms, no wrong values, recovery;
- TDK `trip` and its recovery; TDK power cycle and recovery within 15 s;
- measured update rate of the fast TDK PVs against the line arithmetic at 19200 baud;
- the IOC log contains no database, protocol or link error.

# Notes from the tasks that are already merged
- **Harness**: `emulation/devtest/run.sh <case-directory> [pytest arguments]`. The case directory holds `sim.yaml` (a YAML LIST of simulator entries), `ioc.cmd` and `test_*.py`. `ioc.cmd` may use `$(SIM_HOST)`, `$(MIST2_DB)` and `$(CASE_DIR)`. The harness loads `ioc_info.db` with `P=DEVTEST` and waits for `DEVTEST:heartbeat`. An error in `ioc.cmd` stops the IOC, and the harness then prints the log tails and exits 99. Logs are in `<case-directory>/build/`. Do not run the same case directory twice at the same time.
- **Simulator core**: `emulation/sim/README.md` is the reference. Tests reach the control port with `mist2sim.control.ControlClient`. `get` returns values without noise. A silent unit does not execute what it is sent.
- **Startup files**: an error inside a file loaded with `iocshLoad` does not stop the IOC unless that file starts with `on error break`. The harness adds the line for `ioc.cmd`.
- **Temporary files**: make your own directory with `mktemp -d`. Do not use a shared scratch directory: other engineers write there at the same time.
- **Docker**: three other engineers run their own test cases on this Docker daemon at the same time. Touch only containers and networks of your own runs. Do not rebuild the images unless a file under `EPICS/ioc` or `emulation/docker` changed, and you must not change those.
- **Load**: the unit-test suite contains timing tests with real sockets. If one fails once while the machine is busy and passes when repeated, say so in your report and do not loosen it.

# Rules
- Do not invent protocol details. The manuals decide. What they do not say becomes a setting with a comment and a line in your report.
- Keep it small and readable.
- Leave no container running when you finish.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t4-tdk-naim @ <commit>
    BUILT: one line per deliverable
    PVS: every PV with type, unit and scan, new names marked NEW
    MACROS: every macro of each database with default and meaning, and the dbLoadRecords lines
    SIMULATOR SETTINGS: the configuration keys of both simulator types, with an example each
    SOURCES: which manual (title, revision, URL) settled which part of each protocol
    VERIFIED: the three acceptance commands with exit code and key output
    DECISIONS: choices the brief left open, each with one reason
    ASSUMED: everything the manuals did not settle
    NEEDS THE LEAD: changes outside your files, open questions, anything that did not work
