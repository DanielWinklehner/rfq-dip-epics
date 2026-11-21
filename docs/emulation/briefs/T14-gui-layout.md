You are a GUI designer and engineer on the MIST-2 ion source control system (EPICS). You have one task, T14: propose the page layout of the new operator GUI. A lead engineer wrote this brief, will review your proposal and present it to the project owner (an accelerator physicist who operates this ion source), who then picks one option. Nothing gets built before that decision. Other engineers work in parallel on other files, so stay inside the files you own.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t14`, on branch `emu/t14-gui-layout`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. `/home/daniel/code/rfq-dip-epics` itself is the lead's worktree: never edit, stage or commit anything there. Check that `git -C /home/daniel/code/rfq-dip-epics/.claude/worktrees/t14 branch --show-current` prints `emu/t14-gui-layout` and that `docs/emulation/DESIGN.md` exists in your worktree. If not, stop and report.
- Commit on that branch only. Small commits. Never commit on `master` or `emulated-iocs`. Never push, never open a pull request.
- Files you own: `docs/emulation/gui/` (new). Nothing else.
- Host: WSL2 Ubuntu. `sudo` needs a password, install nothing on the host. Docker works without sudo if you need a tool (for example to render an SVG to PNG to look at your own drawing).

# What to read
1. `docs/emulation/DESIGN.md`: the approved design. Section 3 lists every device with its PV names, section 4 the turbopump controllers.
2. `plan/controls.yaml`: the single source of truth for devices and subsystems. Look at `subsystems`, `devices` (name, model, subsystem, location, status, notes) and `software.gui`. The sketches in `plan/out/overview.svg` and `plan/out/sub_*.svg` show how the devices connect.
3. The existing GUI, whose general look the owner wants to keep:
   - `reference/lab-2023/RAS/` is the newest copy (2023): `Main.js` (tabs), `Home.js`, `Vacuum.js`, `Safety.js`, `BeamlinePage.js`, `Plots.js`, `Devices.js` (the device list with the operators' labels, for example which valve is which, which temperature is which), `Utils/` (one small component per device class, a synoptic attempt in `Utils/Beamline.js`).
   - `RAS/IsoDAR/` is an older copy of the same and `RAS/README.md` explains its structure.
4. React Automation Studio V8.1.0, the toolkit the GUI is built with. Its source may still be at `/tmp/claude-1000/-home-daniel-code-rfq-dip-epics/2922b8dd-456c-4cea-8389-b7ee279f7457/scratchpad/ras_ref/ras` (read only). If that path is gone, clone it into a temporary directory OUTSIDE the repository: `git clone --depth 1 --branch V8.1.0 https://github.com/React-Automation-Studio/React-Automation-Studio`. Find out what it offers that matters for layout: the layout components (`TraditionalLayout` with tabs, others), the base components (text input and output, toggle and action buttons, indicators, graphs), the SVG beamline components, how components show EPICS alarm severity, context menus and probes, theming. Design with what exists there. Where an option needs a custom component, say so.

# The machine, in short
MIST-2 is a filament-driven multicusp ion source on a high-voltage platform, with an electrostatic extraction system, at ground potential a diagnostic box with a Faraday cup, and a vacuum system. What the GUI must show (PV names in DESIGN.md):
- **Plasma generator (on the HV platform)**: filament heating supply (TDK, 8 V 300 A), filament discharge supply (Matsusada REK, 150 V 24 A, soon 55 A), 4 thermocouples.
- **Extraction and optics**: five Matsusada 20 kV supplies: ion source voltage, puller, lens 1, lens 2, and lens 3 (installed, not in use). One "all HV off" command.
- **Vacuum and gas**: mass flow controller (set point and flow), 8 solenoid valve channels (known: foreline valve, MFC shutoff valve, vent valve, Faraday cup actuator), three pressures (foreline gauge "APG", diagnostic box gauge, source ion gauge "nAIM" with an enable), two turbopumps (start/stop, accelerating, at speed, failure, state, and speed and current from a monitor port).
- **Cooling**: sensor box with 7 temperatures and 5 water flows.
- **Diagnostics**: Faraday cup current.
- **Interlocks (old box, a new system follows later)**: two inputs (HV cage doors) and one summary PV that gates the HV and discharge outputs.
- **Infrastructure**: two IOCs with heartbeat and mode (sim or real), and per Arduino-type device an identity (name, firmware, channel list).
Where the physical arrangement is not given by these files (for example the order of electrodes along the beam, where each gauge sits), draw what the files support, mark your assumption in the document, and list it as a question. Do not invent hardware.

# What the owner wants from the new layout
- **One overview page that shows the source as a synoptic**, with live values at the place where they are measured.
- **One page per subsystem**: plasma generator, extraction, vacuum and gas, cooling, diagnostics.
- **Expert pages one click behind**: raw channels, firmware identity, communication state.
- **Color that follows EPICS alarm severity** (NO_ALARM, MINOR, MAJOR, INVALID) instead of thresholds coded into pages. A dead device must look dead, not show its last value.
- **Streamlined code**: one device registry generated from `plan/controls.yaml`, one reusable widget per device class (power supply, valve, gauge, pump, and whatever else you find is a class of its own). So design the pages as arrangements of a small set of widgets.
- **Keep what is good in the existing pages, including their general look.**
- Leave room for, but do not design in detail: a button that prints all values as one PDF, data logging with retention tiers, control loops (first loop: discharge current regulated through the filament heating current).
- The emulator must be unmistakable: when an IOC reports mode `sim`, the GUI says so on every page.
- Used on a control room monitor (wide screen) first. A tablet next to the machine is a plausible second use, a phone is not a target.

# Deliverable: `docs/emulation/gui/LAYOUT.md` plus wireframes
- **Two or three layout options that differ in a real way** (navigation model, how much lives on the overview, how experts get to details), not three color variants of one idea. For each option: the idea in three sentences, what an operator does to complete three everyday tasks (start the plasma and bring up the extraction voltage; find out why a value is purple (INVALID); check vacuum and open the foreline valve), strengths, weaknesses, and what it costs to build with RAS V8.1.0 (which standard components, which custom ones).
- **Wireframes as SVG files** in `docs/emulation/gui/wireframes/`, drawn at 1600 x 900, grayscale boxes with real labels and plausible values, alarm colors used only to show how severity appears. Per option at least: the overview page, one subsystem page (take extraction or vacuum and gas, the same one for all options so that they can be compared), and how the expert view opens. Write the SVG by hand or generate it with a script that you also commit. Look at your own output (render it to PNG and read it) and fix overlaps and cut-off text before you deliver. Every wireframe must be readable on its own: a title, and labels a physicist recognises.
- **One shared part, independent of the option**: the list of widget classes with what each shows and which PVs it takes from the registry; the page-to-device map; how alarm severity is shown (text, border, background, icon; what INVALID and disconnected look like; how the emulator banner looks); what is kept from the old GUI and what is dropped, with a reason each.
- **A recommendation**: which option and why, in one paragraph, and what you would take from the other options.
- **Open questions for the owner**, each answerable in one line.
Write for a physicist, plain and short. No marketing language. The whole document should be readable in ten minutes.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t14-gui-layout @ <commit>, worktree <absolute path>
    FILES: the document and every wireframe with one line on what it shows
    OPTIONS: one line per option, and your recommendation with its main reason
    RAS FINDINGS: what V8.1.0 offers for layout and alarm display that the next engineers must know (file paths inside the RAS source)
    ASSUMED: every assumption about the machine or about RAS that you could not verify
    QUESTIONS: the open questions for the owner
