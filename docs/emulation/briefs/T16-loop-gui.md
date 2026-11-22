You are a front-end engineer on the MIST-2 ion source control system (EPICS, React Automation Studio V8.1.0). You have one task, T16, in three parts: the operator's view of the discharge current loop in the MIST-2 GUI, values that are set in place on the drawings, and tabs that open as windows of their own. The second and third part are wishes of the owner of 2026-11-22. A lead engineer wrote this brief, will run your checks himself, look at the pages, and merge your branch.

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

# The owner's wishes of 2026-11-22, in his words
1. "It looks like on the main screen/tabs, all the PVs are read-only. Only if I click on it and the pop-up appears can I change a value. I would like to be able to set values in place on the main screen."
2. "Would it be possible to pop out individual tabs as separate windows and re-attach them if the user wants to?"
3. He also has a number of comments on the drawings themselves (example: "the filament should be vertically centered, attached to the left wall of the plasma chamber and have its tip point to the right"). These are NOT yours: the lead applies them with the owner after your branch is merged. So rearrange what your changes force you to rearrange, and do not redraw the machine.

Wish 1 changes the decision of gate G2 ("clicking an element opens the device in a window of its own" stays, but the drawing is no longer read-only). It is the owner's to change.

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

R10. **Values set in place (wish 1).** Every tag on the Overview and on the subsystem tabs shows, beside the read-backs it shows today, what the operator sets in normal operation, as fields that work where they stand: a number is typed and sent with Enter; a request (output on or off, valve, pump, mode of the loop) is switched there.
   - Which roles: the set points and requests of the widget's operation group. The saved settings (current limits, gains, the loop's limits and times) stay in the device window. One table per class beside the one that says what a tag reads (`synoptic/tagRows.js`), driven by the registry (`access`, role, `confirm`): nothing coded per page or per device.
   - A number that was typed and not sent is not left standing: Escape or leaving the field shows the IOC's value again. The mouse wheel and the arrow keys do not change a value. Say how a field shows that it holds an unsent entry.
   - The vent valve asks first, as it does in its window. No other dialog (the owner's rule).
   - Alarm look as everywhere. A field whose record is INVALID or not connected looks dead; say whether it still accepts an entry and why.
   - A click on the tag outside its fields still opens the device window. The context menu stays.
   - The loop's tag has its mode request and its set point in place.
   - The tags grow. Rearrange the drawings (`config/drawings.json`) so that nothing overlaps on a 1920 x 1080 monitor. The box "Reserved: control loop" on the plasma generator page goes: the loop is there now.
   - The tags are drawn in SVG today (`synoptic/TagRow.jsx`). How an input gets in there (an HTML layer, `foreignObject`, or something else) is yours: choose what stays sharp and aligned at every window size and say why.
R11. **Tabs as windows (wish 2).** Each tab (Overview, the subsystems, Trends, Infrastructure) can be opened as a browser window of its own and brought back.
   - A browser cannot dock or drag a tab out, so: a small control on the tab opens the page in its own window. That window is complete in itself (page name, the emulator banner, its own severity) and is an ordinary route of the application, so it can also be opened by its address.
   - While a page is out, its tab stays in the bar, marked as open in a window, and still shows the page's worst severity. A click on it brings that window to the front. A control in the window ("attach") closes it and shows the page in the main window again; closing the window by the browser's own button does the same.
   - Windows opened this way close with the main window, as device windows do. A device opened from such a window gets the same one window per device as from the main window.
   - With every page out, the main window still shows the tab bar, the status strip and ALL HV OFF.
   - Say what happens on a reload of the main window, and keep it simple.

Order of work: first the loop's widget with the tags settable in place (they belong together: the loop's tag is the first that needs it), then the tabs. Commit the two parts separately, so that the first can be merged alone if the second runs late.

# Files you own
- `RAS/mist2/ReactApp/src/` and `RAS/mist2/tools/` (checks and screenshots), `RAS/mist2/README.md`
- `docs/emulation/gui/LAYOUT.md`: one short section on the loop widget (what it shows and why), and under "Decision" a dated note of the owner's two wishes and how they are built
Not yours: `plan/`, the registry (generated: if it lacks something the widget needs, a label, words, a role, say exactly what in your report under NEEDS THE LEAD and work with a clear stand-in until then), `EPICS/`, `loops/`, `emulation/`, `docs/emulation/STATUS.md`, `PLAN.md`, `DESIGN.md`, `LOOP.md`.

# Deliverables
1. The widget, the tag, the place on the drawing, the role words; the tags settable in place on every drawing; the tabs as windows.
2. `gui-check.sh` extended and passing as a whole: the loop's records are shown with the values Channel Access reads (check 2 as for every device), and one new check of the loop by the browser: PID requested with the supplies off is refused and the reason is on the screen; with the conditions fulfilled the mode shows PID; a typed set point arrives; MANUAL again. The check leaves the loop in MANUAL and everything as it found it. Without the plant model the measured value does not follow the actuator: the check is about the switching and the display, not about control. For wish 1: on the Overview, a set point typed into a tag arrives at the IOC, an unsent entry is given up with Escape, an output is switched on and off from its tag, and the vent valve asks first from its tag; check 5 of today (the same through the device window) stays. For wish 2: a tab opened as a window shows the values Channel Access reads, its tab in the main window is marked and brings the window to the front, attaching brings the page back, and the windows close with the main window. Check 2 (every device record shown with the value Channel Access reads) and check 6 stay true.
3. Screenshots in `RAS/mist2/tools/screenshots/`: the plasma generator page with the loop in MANUAL and in PID, the device window in PID, the device window after a refusal; every drawing with its new tags (the existing `normal-*.png` renewed), a tag with an unsent entry, a page in its own window beside the main window that marks it.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    flock /tmp/mist2emu.lock bash -c 'make -C emulation up && make -C RAS/mist2 dev-up && RAS/mist2/tools/gui-check.sh; rc=$?; make -C RAS/mist2 dev-down; make -C emulation down; exit $rc'

Exit 0, and nothing is left running. The lead then starts the emulation with the plant, runs the source to 20 A and switches the loop from the GUI.

# Rules
- Do not invent facts about the machine or the loop: what the widget says comes from the registry and from LOOP.md.
- Do not rename or change any PV. No dead code, no component that is used once and wraps nothing.
- Keep the code as small as the existing widgets are: they are a few lines each because the role fields do the work.
- Verify by running, not by reading. Show that the new check fails when the widget is broken (for example with the reason field removed).
- The machine is shared with the logger engineer's test runs. A check that fails once on a time limit and passes when you run it again alone is to be reported with both results, not cured by a wider limit.
- If a requirement turns out to be wrong or two of them collide, do the sensible thing, and say so in the report under DECISIONS.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t16-loop-gui @ <commit>
    BUILT: one line per part
    SHOWN: where each role of the loop appears (tag, Controls, Trend, Settings, Expert)
    IN PLACE: per class, which roles a tag sets, and how an entry is sent, given up and shown
    WINDOWS: how a tab goes out and comes back, and what a reload does
    VERIFIED: the acceptance command with exit code and the count of checks, and how you saw the new check fail
    DECISIONS: choices the brief left open, each with one reason
    NEEDS THE LEAD: what the registry or the plan lacks, text for STATUS.md, open questions
