You are a front-end engineer on the MIST-2 ion source control system (EPICS). You have one task, T11: build the operator GUI. A lead engineer wrote this brief, will run your acceptance test himself, look at every page, and merge your branch. Other engineers work in parallel on other files, so stay inside the files you own.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t11`, on branch `emu/t11-gui`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never edit, stage or commit anything in `/home/daniel/code/rfq-dip-epics` outside your worktree. Check that `git -C /home/daniel/code/rfq-dip-epics/.claude/worktrees/t11 branch --show-current` prints `emu/t11-gui`. If not, stop and report.
- The GUI needs the React Automation Studio sources, which are a git submodule: run `git submodule update --init RAS/mist2/submodules/React-Automation-Studio` in your worktree. Never change a file inside the submodule.
- Commit on that branch only. Small commits with clear messages. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host (there is no Node on the host: everything runs in containers). Docker works without sudo. The images exist already; the first GUI build of a new worktree takes a few minutes.
- You need two things running, and each can exist only once on this machine: the emulation (`make -C emulation up`, fixed network 172.30.0.0/24) and the GUI development stack (`make -C RAS/mist2 dev-up`, host ports 3000, 3001 and 9001). Check with `docker ps` that neither is running before you start them, and stop both when you are done.

# The decision you build to
The owner decided on 2026-11-21 (`docs/emulation/gui/LAYOUT.md`, section "Decision", and `docs/emulation/STATUS.md`, section "Answers of the owner"). Where this section and LAYOUT.md or the wireframes differ, this section wins.

**Layout: option B, with windows instead of a panel.**
- The synoptic is the console. The main window has the app bar with tabs: Overview, one tab per subsystem, Trends, Infrastructure.
- **Clicking an element of a drawing opens that device in a browser window of its own** (not a docked panel, not a dialog inside the page). The window stays until the operator closes it or the main window is closed. Several device windows can be open at the same time. Clicking a device whose window is already open brings that window to the front and does not open a second one. When the main window closes or reloads, the device windows it opened close too.
- The lab computer has **three monitors of about 24 inch** (design for 1920 x 1080 each): the main window fills one, device windows live on the others. The drawing therefore always has the full window. A device window is small (about 480 x 760), complete in itself (device name, the emulator banner, its own severity), and has the three parts of the B panel: Controls, Trend, Expert. It is an ordinary route of the application, so that it can also be opened by its address.
- Subsystem tabs show a larger drawing of that subsystem, with the same click behaviour. Where a subsystem has nothing that a drawing would make clearer (cooling: a list of temperatures and flows), a generated list of the same clickable elements is right. Say where you chose which.
- The expert view is the Expert part of the device window. An overview of all devices with identity and communication state is the Infrastructure tab.

**The machine (drawing: `docs/emulation/gui/reference/mist2-source-and-cross.webp`, look at it):**
- Ion source with a hairpin filament, on the high-voltage platform.
- A conical high-voltage break, then ONE vacuum chamber at ground: a CF 10 inch six-way cross.
- The extraction system sits in the upstream flange of the cross: puller, lens 1, lens 2, lens 3 along the beam. Lens 3 is grounded mechanically and has no supply.
- The Faraday cup comes in from the top flange (valve channel 4 moves it).
- Turbopump 1 is on the bottom flange. Turbopump 2 does not exist in phase 1: the registry flags it `not_installed`. A device with that flag is not drawn and gets no place on a subsystem page. It appears on the Infrastructure tab only, marked as not installed.
- The nAIM and the APG sit side by side on a side flange of the cross. The second channel of the gauge controller (`diag_box`, an AIM gauge) belongs to phase 2 and measures nothing now: show it only in the gauge controller's device window, labelled as in the registry.
- The foreline has no gauge in the control system yet. The vent valve vents the turbopump through its side port. Gas comes from the mass flow controller through the shutoff valve to the source.
- There is no "diagnostic box" and no second chamber. The wireframes are wrong on this point.
- Keep the geometry of every drawing in data, not in code.

**Answers to the open questions of LAYOUT.md section 6:**
- Confirmation dialog ONLY before opening the vent valve. No dialog for high voltage, discharge or turbopump: the high voltage is interlocked. (This replaces requirement 10 below.)
- Dark theme by default.
- No login. Expert views are open to everyone.
- Valve channels 5 to 8 are unused: show them in the valve box's device window only, as spare.
- Labels come from the registry (thermocouples: back plate, filament feedthrough, isolation transformer 1 and 2).
- The cooling water is read by a device whose firmware is not known yet. The sensor box stands in for it and the registry flags it `assumed`: the cooling page says so.

**Changes that are on their way while you work.** Another engineer is reworking the Matsusada supplies on the owner's answers. When that is merged I will tell you, and you take it with `git merge emulated-iocs`. Build so that it costs you nothing:
- There will be four AU supplies (1 source, 2 puller, 3 lens 1, 4 lens 2), not five. Today's registry still has five. Do not write a number of supplies anywhere.
- The current of an AU or REK supply is a LIMIT, not a set point. The registry roles `iset` and `iget` of these supplies will be renamed to `ilimit` and `ilimit_get`. The TDK keeps `iset`: its current really is a set point. Build the Supply widget from the roles a device has: a "current limit" field for `ilimit`, a "current set point" field for `iset`.
- After the interlock opened, the outputs will stay off when it closes again, and their requests will be cleared. Today they still come back by themselves.

**The emulation is yours** for this task: nobody else starts or stops it until you report, except when I ask you to free it for a test run.

# Read first
1. `docs/emulation/gui/LAYOUT.md` in full, with the wireframes in `docs/emulation/gui/wireframes/` (render the SVG files to look at them): the layout options, the parts shared by all options (frame, alarm rules, emulator banner, widget classes, page-to-device map, what is kept from the old GUI), the lead's review at the top, and section 7 on React Automation Studio V8.1.0.
2. `RAS/mist2/ReactApp/src/registry/README.md` and `registry.json`: the generated device registry. It is the ONLY place where the GUI learns about devices, PVs, roles, labels, flags and IOCs.
3. `RAS/mist2/README.md`, `RAS/mist2/UPSTREAM.md`, `RAS/mist2/Makefile`, and the existing shell: `RAS/mist2/ReactApp/src/` (one page that shows heartbeat and mode of both IOCs).
4. `docs/emulation/DESIGN.md` and `docs/emulation/STATUS.md` (open points P1 and following: several of them say how a device behaves and what the GUI must not hide).
5. `reference/lab-2023/RAS/`: the GUI that runs in the lab, whose general look the owner wants to keep (grouped device boxes with a legend, set and read fields side by side, the tab bar).
6. `emulation/sim/README.md`: the simulators' control interface. Your checks use it to inject faults (`mist2sim.control.ControlClient`, from the `tools` container of the emulation).

# What is known about React Automation Studio V8.1.0 (verified in this project)
- A PV is named plainly (`pv="TDK:voltage:read"`), macros are string replacement. The old `pva://` prefix is not needed.
- A component gets `alarmSeverity` 0 to 3. The stock components (`TextOutput`, `TextInput`, `TextUpdate`, the SVG beamline components) colour MINOR and MAJOR only. **INVALID (3) is not handled by any of them and shows the last value in plain style.** A lost Channel Access connection is handled (PV name with a disconnect icon).
- The pvServer sends severity and time stamp but not the alarm status: read `<record>.STAT` as a PV of its own where you need it.
- Long strings (the channel list of a device) are read from the field `VAL$`.
- Routes are in `ReactApp/src/AppRoutes.jsx` (react-router 7). `TraditionalLayout` gives the app bar with tabs. Custom components go under `ReactApp/src/`, RAS components are imported as `React-Automation-Studio/components/...`. The development server reloads on save.
- `StyledIconIndicator` colours by value and ignores severity.

# Requirements
1. **The layout as decided above**, with the page-to-device map of LAYOUT.md 1.5 and every device of the registry on its page. A device that is added to the registry later must appear on its subsystem page and get its expert page WITHOUT a code change: pages are generated from the registry (class, page, roles, labels), not written per device. Only the synoptic is drawn by hand.
2. **One widget per device class** (LAYOUT.md 1.4), taking a device id and nothing else. The registry's roles tell it which PVs to use. A role that a device does not have is simply not shown.
3. **No PV name in the application code.** Not as a string, not as a prefix, not as a template. The only exception is none: the IOC heartbeat and mode PVs are in the registry too.
4. **Alarm display** as in LAYOUT.md 1.2, from the severity of the record only: no thresholds in the GUI. INVALID replaces the number by the word INVALID. Disconnected looks different from INVALID. One shared piece of code decides how a severity looks, and every widget uses it, including lamps and synoptic tags.
5. **Emulator banner** on every page when any IOC reports mode `sim` or its mode cannot be read (LAYOUT.md 1.3), and `[SIM]` in the browser tab title.
6. **Always visible**: "ALL HV OFF", the IOC status chips, the interlock summary.
7. **Expert page per device**, generated from the registry: every PV of the device (internal ones included, marked) with value, severity, status and time stamp, the identity of libcom1 devices (name, firmware, full channel list), the IOC it lives on, and the registry's flags and notes. No "inject fault" buttons, no measured poll rates (see the lead's review in LAYOUT.md).
8. **What the registry flags, the GUI shows**: a supply that is installed but not polled is greyed and says so, a device that runs on assumptions carries a visible mark with the reason from the registry.
9. **Do not hide how the devices behave** (STATUS.md): show the output REQUEST and the output STATE of a supply side by side; show the current-limit echo next to the current set point (enabling an output sets it to 100 %); a turbopump shows its three contacts and its state; the age of the turbopump's monitor record is visible.
10. **Confirmation** before switching a high-voltage or discharge output on, opening the vent valve, and stopping a turbopump. None for switching off or closing.
11. **Trends**: on each subsystem page the trends named in LAYOUT.md, on monitors (no 100 ms polling).
12. **Room for later, not built**: a disabled "PDF report" button in the app bar, and on the plasma generator page a marked place for the control loop.
13. **Streamlined code**: no dead code, no commented-out code, no component that is used once and wraps nothing, no copy of a RAS component where a wrapper does it. Follow the style of the RAS sources (function components and hooks, MUI).

# Files you own
`RAS/mist2/ReactApp/src/` except `registry/` (generated), `RAS/mist2/ReactApp/package.json` only if a dependency is really needed (say which and why), `RAS/mist2/tools/` (your check scripts), `RAS/mist2/README.md`. Nothing else. If the registry lacks something the GUI needs (a role, a label, a page), do NOT put it into the GUI: report it, and say exactly what should be added to `plan/controls.yaml`.

# Checks you deliver (`RAS/mist2/tools/gui-check.sh`)
A script that the lead runs with the emulation and the GUI stack up. It uses a headless browser in a container (the image `mcr.microsoft.com/playwright:v1.59.1-noble` is on this machine) and the simulators' control interface, and exits non-zero on any failure:
- every page and every expert page loads without a JavaScript error or warning from our code;
- every PV of the registry that belongs on a page is shown there with a live value (compare with a value read through Channel Access in the same check);
- with a simulator made silent, the widgets of its devices show INVALID, the tab or tile shows the worst severity, the rest of the GUI stays normal, and after the fault is cleared everything returns;
- with an IOC stopped (the script may stop and start the IOC container), its devices show "disconnected" and the banner changes;
- a set point typed into the GUI arrives at the device, an output is switched on through the confirmation dialog, "ALL HV OFF" works;
- the source code contains no PV name (search the sources for every PV name and prefix in the registry);
- a screenshot of every page in normal state and of the fault state is saved under `RAS/mist2/tools/screenshots/` (commit them: the owner looks at them).

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    make -C emulation up
    make -C RAS/mist2 dev-up
    RAS/mist2/tools/gui-check.sh
    make -C RAS/mist2 dev-down
    make -C emulation down

All exit 0. The lead then opens `http://localhost:3000/` in a browser and goes through every page himself.

# Rules
- Build it in this order and commit after each step: alarm display and registry access; the widget classes on one plain page with every device; the subsystem pages; the expert pages; the overview synoptic; the checks. Run the check script after each step.
- Where the machine's physical arrangement is an assumption (LAYOUT.md section 8), keep the synoptic's geometry in one data file, so that correcting it is editing numbers, not code.
- Do not invent hardware or PVs. Do not hard-code a value, a limit or a unit that the record provides.
- Leave nothing running when you finish.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t11-gui @ <commit>
    BUILT: the pages and the widget classes, one line each
    STRUCTURE: the source tree with one line per file
    VERIFIED: the acceptance commands with exit code and the summary of gui-check
    SCREENSHOTS: the list
    REGISTRY GAPS: what the GUI needed and the registry did not have, and what you did instead
    DEVIATIONS: where the result differs from LAYOUT.md or the wireframes, and why
    DECISIONS: choices the brief left open, each with one reason
    NEEDS THE LEAD: changes outside your files, open questions
