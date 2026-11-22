You are a front-end engineer on the MIST-2 ion source control system (EPICS, React Automation Studio V8.1.0). You have one task, T16: the operator's view of the discharge current loop in the MIST-2 GUI. A lead engineer wrote this brief, will run your checks himself, look at the pages, and merge your branch.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t16`, on branch `emu/t16-loop-gui`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never edit, stage or commit anything in `/home/daniel/code/rfq-dip-epics` outside your worktree.
- The GUI needs the React Automation Studio sources, a git submodule: run `git submodule update --init RAS/mist2/submodules/React-Automation-Studio` in your worktree. Never change a file inside the submodule. Copy `RAS/mist2/.env` from `/home/daniel/code/rfq-dip-epics/RAS/mist2/.env` if your worktree has none (it is not committed).
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host (there is no Node on the host: everything runs in containers). Docker works without sudo. The images exist.
- **Shared machine.** Another engineer works on the data logger in another worktree at the same time and uses the same emulation. The emulation (fixed container names, network 172.30.0.0/24) and the GUI development stack (host ports 3000, 3001, 9001) can each exist only once. Rule for both of you: take the lock for the whole time you have the emulation up, and bring down what you started before you release it. In practice one command: `flock /tmp/mist2emu.lock bash -c '<start>; <work>; <stop>'`. Never leave the emulation or the GUI stack running outside the lock, and never stop containers you did not start. If the lock is taken, wait: the other engineer's test runs take up to 30 minutes.

# Read first
1. `docs/emulation/LOOP.md`: the loop, its two layers, every record, the hand-back and refusal rules.
2. `docs/emulation/gui/LAYOUT.md`: the decision at the top (synoptic as console, a device opens in a browser window of its own), sections 1.2 (alarm severity), 1.4 (widget classes: room was left for a loop class), 1.5, and section 7 (what is known about React Automation Studio V8.1.0).
3. `RAS/mist2/README.md` and `ReactApp/src/`: `registry.js`, `roles.js`, `components/devices/` (one widget per registry class, built from roles), `components/RoleField.jsx`, `components/fields/`, `components/TrendSet.jsx`, `synoptic/` (`layout.js`, `tagRows.js`), `config/drawings.json`, `pages/DeviceWindow.jsx`, `pages/SubsystemPage.jsx`.
4. `RAS/mist2/tools/gui-check.sh`, `gui-check.mjs`, `gui_check_ca.py`: the GUI's check against the running emulation.
5. The registry entry of the loop: device `dis_loop` of class `loop` in `ReactApp/src/registry/registry.json` (generated from `plan/controls.yaml`; `plan/README.md` says how).

# Where things stand
The loop is built and merged: records `LOOP-DIS:*` in the platform IOC, the PID in the container `loop`. The registry has it as a device of the new class `loop` on the page "Plasma generator". The GUI has no widget for that class: it falls back to the widget of a controller, which shows nothing of the loop, and `gui-check.sh` fails on it.

# Goal
The operator runs the loop from the GUI. On the plasma generator page he sees at one glance whether the loop is in MANUAL or PID, and why it last handed back. In the loop's device window he switches it, sets the set point, sees every condition, and has what he needs to tune it.

# Requirements
R1. **A widget for the class `loop`**, built from the roles of the registry like the other widgets. No PV name and no PV prefix in the application sources (check 6 of `gui-check.sh`). A second loop in the registry appears without a change to the code.
R2. **Operation**, in the device window's Controls part, in this order of importance: the mode request beside the mode; the reason of the last hand-back or refusal as its word, right there, not in the Expert part; the set point beside the measured value; the output beside the error; the flag "output at a limit"; whether the loop service is alive; the three permit conditions, each named as the registry names it and shown fulfilled, not fulfilled or without data.
R3. **A refusal is seen.** When the operator requests PID and a condition is missing, the request returns to MANUAL within a cycle of the service (0.2 s). The operator must see why without looking for it. Show how in your report, with a screenshot.
R4. **Tuning.** The three terms. A trend in the device window with the measured value and the set point on one axis and the output on another (or in a second trend below: decide and say why), fast enough to tune by: the loop's records change five times per second in PID.
R5. **Settings**, as a group of their own headed like the supply's ("saved by the IOC"): gains, derivative filter time, output limits, slew, the set point limits, the two times.
R6. **The tag on the plasma generator page**: mode, set point and measured value at least. Place the loop on the drawing where it belongs, between the discharge supply (what it measures) and the filament heating supply (what it sets), with the geometry in `config/drawings.json` as for every other element. While the loop is in PID the operator should see on the drawing that the filament heating current is the loop's: decide how, with the least code (for example by the tag alone), and say what you chose.
R7. **Alarm severity as everywhere** (LAYOUT.md 1.2): the fields follow the severity of their records; a loop service that is not alive (MAJOR) shows on the tab and on the tag; INVALID looks dead. Nothing coded per page.
R8. **Role words.** The labels of the new roles come from the role table (`roles.js`) or from the registry, in operator's words. If a role of the loop collides with the meaning of an existing role, do not bend the existing one: report it.
R9. **No confirmation dialog** for PID (the owner's rule: a dialog only before opening the vent valve). The loop has its own permits.

# Files you own
- `RAS/mist2/ReactApp/src/` and `RAS/mist2/tools/` (checks and screenshots), `RAS/mist2/README.md`
- `docs/emulation/gui/LAYOUT.md`: one short section on the loop widget (what it shows and why)
Not yours: `plan/`, the registry (generated: if it lacks something the widget needs, a label, words, a role, say exactly what in your report under NEEDS THE LEAD and work with a clear stand-in until then), `EPICS/`, `loops/`, `emulation/`, `docs/emulation/STATUS.md`, `PLAN.md`, `DESIGN.md`, `LOOP.md`.

# Deliverables
1. The widget, the tag, the place on the drawing, the role words.
2. `gui-check.sh` extended and passing as a whole: the loop's records are shown with the values Channel Access reads (check 2 as for every device), and one new check of the loop by the browser: PID requested with the supplies off is refused and the reason is on the screen; with the conditions fulfilled the mode shows PID; a typed set point arrives; MANUAL again. The check leaves the loop in MANUAL and everything as it found it. Without the plant model the measured value does not follow the actuator: the check is about the switching and the display, not about control.
3. Screenshots in `RAS/mist2/tools/screenshots/`: the plasma generator page with the loop in MANUAL and in PID, the device window in PID, the device window after a refusal.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    flock /tmp/mist2emu.lock bash -c 'make -C emulation up && make -C RAS/mist2 dev-up && RAS/mist2/tools/gui-check.sh; rc=$?; make -C RAS/mist2 dev-down; make -C emulation down; exit $rc'

Exit 0, and nothing is left running. The lead then starts the emulation with the plant, runs the source to 20 A and switches the loop from the GUI.

# Rules
- Do not invent facts about the machine or the loop: what the widget says comes from the registry and from LOOP.md.
- Do not rename or change any PV. No dead code, no component that is used once and wraps nothing.
- Keep the code as small as the existing widgets are: they are a few lines each because the role fields do the work.
- Verify by running, not by reading. Show that the new check fails when the widget is broken (for example with the reason field removed).
- If a requirement turns out to be wrong or two of them collide, do the sensible thing, and say so in the report under DECISIONS.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t16-loop-gui @ <commit>
    BUILT: one line per part
    SHOWN: where each role of the loop appears (tag, Controls, Trend, Settings, Expert)
    VERIFIED: the acceptance command with exit code and the count of checks, and how you saw the new check fail
    DECISIONS: choices the brief left open, each with one reason
    NEEDS THE LEAD: what the registry or the plan lacks, text for STATUS.md, open questions
