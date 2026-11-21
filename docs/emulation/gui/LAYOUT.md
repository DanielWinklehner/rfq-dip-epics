# GUI layout proposal (T14, gate G2)

Three layouts for the new MIST-2 operator GUI. All three use the same frame, the same alarm
rules and the same widget classes (section 1). They differ in how an operator moves around and
reaches the details (sections 2 to 4). Pick one, or one with parts of another (section 5).
Nothing is built before that decision.

Wireframes are in [wireframes/](wireframes/). Each is 1600 x 900 (the control room monitor),
grayscale, with alarm colours only where they show a severity. All values are made up.
`wireframes/make_wireframes.py` regenerates them (Python standard library only).

| File | Shows |
|---|---|
| `S1_widgets_and_severity.svg` | Shared: alarm severity on fields, tags and lamps; emulator banner; the widget classes |
| `A1_overview.svg`, `A2_vacuum.svg`, `A3_expert.svg` | Option A: overview, Vacuum and gas tab, expert page |
| `B1_overview.svg`, `B2_vacuum.svg`, `B3_expert.svg` | Option B: overview with panel, Vacuum and gas tab, expert tab of the panel |
| `C1_overview.svg`, `C2_vacuum.svg`, `C3_expert.svg` | Option C: overview with tiles, Vacuum and gas table, Extraction with expert mode on |

The wireframes all show one machine state: Lens 2 (AU unit 5) has stopped answering, so its
read-backs are INVALID, and the magnet plate thermocouple is in MINOR. Everything else is normal.

## 1. Shared by all options

### 1.1 Frame

- **App bar**: RAS `TraditionalLayout` with `denseAppBar`, as in the 2023 GUI. It carries the
  title, the navigation (tabs in A and B), **ALL HV OFF** (`AU:alloff:set`, always visible),
  a placeholder for **PDF report** (WP8) and the RAS menu (theme, login).
- **Status strip** below the app bar on every page: the emulator banner on the left; on the
  right one chip per IOC (mode and heartbeat) and the interlock summary (`interlock_open`,
  door inputs).
- Pages stay mounted when the operator switches (the `display: none` trick in the 2023
  `Main.js`), so trends keep their history.

### 1.2 Alarm severity

Colour comes only from the record's severity, never from limits written into a page. Silent
devices turn their records INVALID (DESIGN.md section 2); alarm limits such as HIGH/HIHI on the
pressures belong in the databases (`controls.yaml`, gauge notes).

| State | Value field | Synoptic tag, table row | Lamp |
|---|---|---|---|
| NO_ALARM | plain | plain | dark = on, hollow = off |
| MINOR | amber fill, amber border, ▲ after the unit | amber row, ▲ | amber |
| MAJOR | red fill, red border, ■ after the unit | red row, ■ | red |
| INVALID | purple fill and border, the number is **replaced by the word INVALID**, "?" | purple; whole tag purple if the device is silent | purple ring |
| Disconnected (no Channel Access) | grey, dashed border, "no connection", × | grey dashed | grey with a stroke |

- **A dead device looks dead.** Two ways to die: the IOC runs but the device does not answer
  (records go INVALID), or the IOC or network is gone (CA disconnects). Neither shows a bare
  old number. The last good value and its time are in the expert view.
- The marker and the word carry the state as well as the colour, for grayscale printouts and
  colour-blind readers.
- Tabs, tiles and the rail show the **worst severity** of everything on that page as a dot.
- Lamps for binary states (valve read-back, turbo relays) use the same colours for their
  severity. The turbo failure relay is MAJOR in the database, so it turns the lamp red.

### 1.3 Emulator banner

- Shown on every page when **any** IOC reports mode `sim`, or when a mode PV is disconnected
  (unknown counts as "not real").
- Blue diagonal stripes, a colour no alarm uses, with the text "EMULATOR — rack IOC and HV IOC
  report mode sim. No hardware is connected." Mixed case: "MIXED — rack IOC in mode sim, HV IOC
  on real hardware". The browser tab title gets the prefix `[SIM]`. The wireframes draw the
  banner in grey; `S1` shows the colour.
- The mode comes from each IOC's mode PV, not from a GUI setting. The PDF report (WP8) should
  print the same line.
- In sim mode only, expert views show **Inject fault** and **Clear fault** buttons that talk to
  the simulator's control port. They are not rendered with real hardware.

### 1.4 Widget classes

One React component per class. Each takes a device id; the PV names come from the registry
generated from `plan/controls.yaml` (T10). Roles in the right column are the registry keys
the widget asks for.

| Class | Devices | Shows | PVs (role: name) |
|---|---|---|---|
| **Supply** | TDK, REK, AU 1 to 5 | set and read V and I, output request and state, power. TDK also mode and fault | `vset` `:voltage:setpoint`, `iset` `:current:setpoint`, `vread` `:voltage:read`, `iread` `:current:read`, `out_cmd` `:SetToggleOutput` (TDK `:status:setpoint`), `out_state` `:read_output_status` (TDK `:status:get`), `power` `:power:read` (TDK `:power:get`), expert: `:voltage:get`, `:current:get`, `:status:read`, TDK `:mode:get`, `:fault:get` |
| **Valve** | valve box channels 1 to 8 | command and read-back, words per valve (OPEN/CLOSED, IN/OUT) | `cmd` `VALVE:s<n>:set`, `state` `VALVE:s<n>:get` |
| **Gauge** | nAIM, APG, diagnostic box | pressure in exponent format, enable if the gauge has one | `p` `AIM:getpressure`, `PRESSURE:apg:getpressure`, `PRESSURE:diag_box:getpressure`; `enable` `AIM:enable` |
| **Turbo pump** | Turbo 1, Turbo 2 | run/stop, three relay lamps, state, speed, current, age of the RS-232 record | `TURBO<n>:start:set`, `:start:get`, `:accel:get`, `:atspeed:get`, `:failure:get`, `:state:get`, `:speed:get`, `:current:get`, `:age:get`; expert `:raw:get` |
| **Mass flow controller** | MFC | set point, set point read-back, flow | `MFC:setSP`, `MFC:getSP`, `MFC:getFlow`; expert `MFC:setWink`, `MFC:getWink` |
| **Reading** | thermocouples, sensor box temperatures and flows, Faraday cup current | one value with label and unit | `THM:t<n>:get` (expert `THM:j<n>:get`, `THM:f<n>:get`), `SENSOR:t<n>:gettemp`, `SENSOR:f<n>:getflow`, `FC:current:get` |
| **Interlock** | old interlock box, later the new system | inputs and permit | `INTLK:i1:get_interlock`, `INTLK:i2:get_interlock`, `interlock_open`; later `ilk:*` |
| **IOC status** | rack IOC, HV IOC | mode, heartbeat; MAJOR after 5 s without a beat | names not defined yet (section 8) |
| **Device info** (expert) | every device | identity, chain and unit, last good reply, every record with value, SEVR, STAT, time stamp | `<P>:id`, `:firmware`, `:channels` for libcom1 and Opta devices; `<record>.SEVR`, `<record>.STAT` |
| **Command** | ALL HV OFF, later interlock reset and report trigger | one button | `AU:alloff:set` |
| **Trend** | any | time-stamped graph | RAS `GraphY` |
| **Synoptic symbols** | overview, subsystem drawings | electrode, valve, gauge, pump, cup, value tag | the same roles as the classes above |

Each class has a card form (fields, as in the 2023 GUI), a tag form (synoptic) and a row form
(tables, option C). Room is left for a **Loop** class (WP10: enable, mode, set point, output,
limits) next to the TDK and REK on the plasma page.

### 1.5 Pages and devices

| Page | Devices |
|---|---|
| Overview | all of them, as a synoptic (amount of detail depends on the option) |
| Plasma generator | TDK, REK, thermocouples t1 to t4; MFC as a copy (question 9); later the discharge loop |
| Extraction | AU 1 source, AU 2 puller, AU 3 lens 1, AU 5 lens 2, AU 4 lens 3 (greyed, not polled); ALL HV OFF; interlock permit |
| Vacuum and gas | nAIM, APG, diagnostic box gauge; Turbo 1 and 2; MFC; valve channels 1 to 8; roughing pump placeholder |
| Cooling and interlocks | sensor box t1 to t7 and f1 to f5; interlock inputs and summary; later the new interlock with first fault |
| Diagnostics | Faraday cup current, cup actuator (valve 4), diagnostic box gauge |
| Trends | any PV, picked from the registry; later the archiver |
| Expert / infrastructure | IOC heartbeat and mode, identity of every Arduino or Opta device, raw channels, simulator faults |

### 1.6 From the 2023 GUI

| Kept | Why |
|---|---|
| `TraditionalLayout` with a dense app bar and tabs (A, B) | Operators know it; it is stock RAS |
| Pages stay mounted while hidden | Trends keep their history |
| The fieldset-and-legend card per device (`PowerSupply.js` and others) | Reads well and is the "look" to keep |
| `TextInput` / `TextOutput` with label, units and `alarmSensitive` | Standard RAS, already severity-aware for MINOR and MAJOR |
| Output toggle plus output-state indicator on every supply | Command and read-back side by side |
| Operator labels from `Devices.js`: foreline, MFC shutoff, vent, Faraday cup valves; HV door lower/upper; back plate, magnet plate; turbo pump, front plate, Faraday cup 1 flows | They are the operators' names; they move into `controls.yaml` |
| Time-stamped trends of AU voltages and currents, pressures with exponent ticks | Used daily |
| The nAIM "Strike" toggle | Becomes the gauge enable |

| Dropped | Why |
|---|---|
| `Tank` widgets for temperatures | A fixed 0 to 100 °C scale is a limit written into the page, and they take a lot of space. A number with severity says more |
| `PowerSupply.js` and `REKPowerSupply.js` as two components | One Supply class |
| PV strings in `Devices.js` | All names come from the registry |
| Units written in the page (`mA` on the TDK, whose current is in A) | Units come from the record's EGU |
| `testIOC` and `amplitude` placeholders (Safety, Beamline, MFC) | Not real channels |
| `Utils/Beamline.js` (dipole and steerers) | Another machine; replaced by the MIST-2 synoptic |
| The Plots tab with one graph per supply | Trends go on the subsystem pages, plus one Trends page |
| The Safety tab mixing interlocks, flows, temperatures and pressures | Split into Cooling and interlocks and Vacuum and gas |
| Local copies `ModGraphY.js`, `ModContextMenu.js` | Use V8.1.0 `GraphY` and `ContextMenu` unless T11 finds a feature missing |
| Graph polling every 100 ms | Update on monitors; keep polling only where a flat line must still scroll |

## 2. Option A: tabs and cards

**Idea.** The 2023 GUI, put in order. A row of tabs: Overview, one tab per subsystem, Trends.
The overview is a full synoptic with every value, set points included; the subsystem tabs are
grids of device cards with trends below; every card has an "expert ›" link to a generated
expert page for that device.

**Everyday tasks**

1. *Start the plasma and bring up the extraction.* Vacuum & gas tab: MFC set point, valve 2
   open. Plasma tab: TDK current and output on, REK and output on (or all on the Plasma tab if
   the MFC copy is wanted). Extraction tab: AU 1, puller, lenses, outputs on. Overview to watch.
   Three tab changes.
2. *Why is a value purple?* The Lens 2 tag on the overview is purple. Click it: the Extraction
   tab opens with the Lens 2 card. Click "expert ›": the expert page says INVALID since 14:02:11,
   STAT TIMEOUT, unit 5 silent while Lens 1 on the same chain answers (`A3`). Two clicks.
3. *Check the vacuum and open the foreline valve.* Pressures and turbo states are on the
   overview. Vacuum & gas tab, Valves card, "1 Foreline" OPEN, read-back lamp follows (`A2`).
   Two clicks.

**Strengths.** Closest to today: no retraining. Cards are generated from the registry with no
hand layout per page. Tabs and cards reflow for a tablet (scrolling tab bar, cards stack).
Expert pages are ordinary routes: a second browser tab can keep one open.

**Weaknesses.** Starting the source means three tabs. The overview is dense because it carries
every number. The expert page replaces the page the operator came from (or needs a second
browser tab).

**Cost with RAS V8.1.0.** Standard: `TraditionalLayout` (tabs), `TextInput`, `TextOutput`,
`ToggleButton`, `ActionButton`, `GraphY`, `BeamLineCanvas`, `ContextMenu` and Probe, MUI
`Grid`. Custom: the shared parts of section 1 (severity wrappers, synoptic symbols, the widget
classes, status strip), one `/expert/:device` route generated from the registry. Lowest cost of
the three.

## 3. Option B: synoptic with a detail panel

**Idea.** The drawing is the console. Clicking any element of the synoptic opens a panel on the
right with that device's controls, a short trend and an Expert tab; the drawing stays visible
and live. Subsystem tabs show a larger drawing of that subsystem with the same panel, so all
controls are reached by pointing at the machine.

**Everyday tasks**

1. *Start the plasma and bring up the extraction.* All from the overview: click the MFC tag,
   set; click the TDK, set and switch on; click the REK; click AU 1, puller, lenses. The drawing
   shows each response. No page change, one click per device.
2. *Why is a value purple?* Click the purple Lens 2 tag: the panel already shows the diagnosis
   line (`B1`). The Expert tab lists every record with SEVR, STAT and time (`B3`). One or two
   clicks.
3. *Check the vacuum and open the foreline valve.* Vacuum & gas tab or overview, click valve 1:
   the panel shows OPEN/CLOSE next to the values that matter for that decision (foreline
   pressure, both turbos, vent valve) (`B2`). Two clicks.

**Strengths.** Fewest clicks; the operator never loses sight of the machine. The panel can put
related values next to a command (context taken from the registry). Expert data is one click
away without leaving the page.

**Weaknesses.** The synoptic must hold every device that can be controlled, and with the panel
open it gets small (`B1` runs it at 94 %, `B3` at 70 %). Five drawings to design and keep
correct instead of one. Two devices cannot be edited side by side. On a tablet the panel covers
the drawing. Furthest from the 2023 look.

**Cost with RAS V8.1.0.** Standard as A, plus the click-to-edit pattern of
`ControlScreens/BeamlineControlSystem.jsx` (`handleOnClick` on SVG components, an editor chosen
by type). Custom: the panel (MUI `Drawer`, persistent, with tabs), clickable versions of every
synoptic symbol, four subsystem drawings in addition to the overview, the context lists per
device. Highest cost.

## 4. Option C: side rail, tables and expert mode

**Idea.** A permanent rail on the left lists the pages, each with its worst-severity dot. The
overview is a row of subsystem tiles (state and three key values each) above a compact synoptic;
subsystem pages are tables with one row per channel and trends on the right. An "Expert" switch
in the app bar adds columns (PV name, SEVR/STAT, update time) and device header rows (chain,
unit, poll rate) to the same tables on every page.

**Everyday tasks**

1. *Start the plasma and bring up the extraction.* Rail: Vacuum & gas row "MFC set point",
   valve 2. Rail: Plasma generator rows. Rail: Extraction rows. Set points in a column can be
   entered one after the other with the Tab key.
2. *Why is a value purple?* The Extraction tile and rail dot are purple. Click: the Lens 2 rows
   are purple. Switch Expert on: STAT TIMEOUT, last reply 14:02:11, chain and unit in the device
   row (`C3`). Two clicks.
3. *Check the vacuum and open the foreline valve.* Rail: Vacuum & gas. Pressures and turbos
   are the first rows, valve 1 further down; OPEN (`C2`). Two clicks.

**Strengths.** The most compact and the most regular: a page is a list of rows generated from
the registry, so a new device appears with no layout work. The tiles answer "is anything wrong"
at a glance. One switch for expert data everywhere, no separate pages.

**Weaknesses.** Tables are less pleasant than cards for a physicist used to the 2023 look. The
rail takes 200 px. Expert mode left on by one person changes every page for the next. The
synoptic is secondary, with fewer values.

**Cost with RAS V8.1.0.** Standard: `TraditionalLayout` without tabs (app bar only),
`TextUpdate`, `TextInput`, `ToggleButton`, `GraphY`, MUI `Table` (as in
`ControlScreens/Components/ControlTable.jsx`). Custom: the rail (MUI `Drawer` variant
permanent, as `SideDrawer.jsx` is a temporary drawer), the row renderer per widget class,
the expert-mode context, worst-severity aggregation for tiles and rail. Medium cost.

## 5. Recommendation

**Option A, with three pieces from the others.** A matches what you asked for one to one
(synoptic overview, one tab per subsystem, expert pages one click behind), keeps the 2023 look,
works on a tablet and costs least, which leaves time for the parts that matter in every option:
INVALID handling, the registry and a correct synoptic. From C take the **worst-severity dot on
each tab** and the **table form for the expert page** (both cheap). From B take the
**diagnosis line** on a device in INVALID (silent since, STAT, state of the other units on the
same chain) and the **context values next to a command** (foreline pressure and turbo states
in the Valves card). If after a few weeks the tab changes during start-up annoy, a B-style panel
can be added to the A overview later without redoing the pages, because both use the same
widget classes.

## 6. Open questions for the owner

1. Which option: A, B, C, or A with the pieces of section 5?
2. Order of the electrodes along the beam: puller, lens 1, lens 2, lens 3. Correct?
3. Where are the gauges: nAIM on the extraction vessel, the diagnostic box gauge on the
   diagnostic box, the APG on the common foreline?
4. Which chamber does each turbo pump (assumed: Turbo 1 extraction vessel, Turbo 2 diagnostic box)?
5. Which chamber does the vent valve (channel 3) vent?
6. Does the gas line run from the MFC in the rack across an insulating break to the platform?
7. Names for TC 1 and TC 4, the sensor box temperatures t1 to t7 and flows f1 and f5? Which
   turbo does the "turbo pump" flow cool?
8. Valve channels 5 to 8: unused, or connected?
9. Show the MFC controls on the Plasma generator page as well?
10. Confirmation dialog before opening a valve, switching an HV output on, stopping a turbo: yes or no?
11. Light or dark theme on the control room monitor?
12. Expert views for everyone, or only after login (RAS has roles)?
13. Is "doors closed, permit yes" in the status strip on every page what you want from the old
    interlock box?

## 7. What the next engineers must know about RAS V8.1.0

Paths below are under `ReactApp/src/components/` in the RAS source.

- **INVALID is not handled anywhere.** All base and SVG components colour only
  `alarmSeverity === 1` (MINOR) and `=== 2` (MAJOR): `BaseComponents/TextOutput.tsx` (around
  line 82), `TextInput.tsx`, `TextUpdate.tsx`, `Gauge.tsx`, `Tank.tsx`, `ProgressBar.tsx`,
  `SvgBeamlineComponents/*.tsx`. Severity 3 falls through to the plain style and **shows the
  last value**. Every option needs thin wrappers (or a patched copy) that handle 3, and a theme
  entry `palette.alarm.invalid` next to `alarm.minor` and `alarm.major`
  (`UI/Themes/*.js`, for example `oceanTheme.js`).
- **Disconnects are handled**: `SystemComponents/EpicsPV.tsx` sets `initialized: false` when
  the pvServer reports `connected: "0"`, and `TextOutput` then shows the PV name with a
  `LanDisconnect` icon instead of the value (`SystemComponents/Widgets/Widget.tsx`,
  `disconnectedIcon`).
- **STAT is not sent.** `pvServer/pvServer.py` (`on_change_value`) passes `severity` and
  `timestamp`, not `status`. The expert view must read `<record>.STAT` as a separate PV.
- `Widget.tsx` has `alarmPv` (take severity from another PV) and `useStringSeverityMatch` /
  `stringSeverity` (map a value to a severity in the page). Do not use the second: it puts
  limits back into pages.
- `BaseComponents/StyledIconIndicator.tsx` (the 2023 interlock lamps) colours by value with
  `onColor`/`offColor` and ignores severity. The lamp needs a custom component.
- **Layout**: `UI/Layout/ComposedLayouts/TraditionalLayout.tsx` has `tabs`, `tabValue`,
  `handleTabChange`, `drawerItems` (left drawer, temporary), `moreVertDrawerItems`,
  `showFooter` / `footerContents` and `denseAppBar`. There is no permanent side rail and no
  slot below the app bar: the status strip is rendered as the first child of the page.
- **Context menu and Probe come free**: every `Widget` opens `SystemComponents/ContextMenu.jsx`
  on right-click (copy PV name, Probe at route `/Probe`), unless `disableContextMenu`.
- **Synoptic**: `SvgBeamlineComponents/` has `BeamLineCanvas`, `HorizontalBeamline`, magnets,
  steerers, `FC.tsx` (cup with in/out actuator), `Harp`, `SlitXY`. Nothing for electrodes,
  valves, gauges or pumps. `ExperimentalSvgBeamlineComponents/SvgComponent.tsx` is the
  template for new ones (PV, alarm, label, `handleOnClick`).
- `ControlScreens/BeamlineControlSystem.jsx` is the working example of click-on-drawing opens
  an editor (option B).
- `ArchiverDataViewer/` reads an EPICS Archiver Appliance through the pvServer
  (`archiverURL`). Relevant for the WP9 choice: with a time-series database instead, RAS trends
  of history need their own code. `LoadSaveComponent/` (save and restore of set points, MongoDB)
  overlaps with the WP8 JSON snapshot. `SystemComponents/IsPrinting.jsx` detects print mode.

## 8. Assumptions

About the machine (all marked in the wireframes as drawn, all in section 6):

- Electrode order puller, lens 1, lens 2, lens 3; lens 3 drawn at its place but greyed.
- nAIM on the extraction vessel ("source" pressure in the 2023 label), diagnostic box gauge on
  the diagnostic box, APG on a common foreline between the turbos and the roughing pump.
- Turbo 1 on the extraction vessel, Turbo 2 on the diagnostic box, one foreline valve for both.
- Vent valve on the extraction vessel. Gas from the MFC through valve 2 and an insulating break.
- "Front plate" water cools the plasma electrode region; the thermocouples sit on the source body.
- Roughing pump drawn without PVs (none exist yet).
- The ion source voltage (AU 1) sets the platform potential. Values are positive numbers
  (D3).
- IOC heartbeat and mode PVs exist by the time the GUI is built (their names are not in
  DESIGN.md).

About RAS (read in the source, not run):

- A field PV such as `AU-20P7-5:voltage:read.STAT` can be subscribed through the pvServer like
  any other PV.
- `severity` arrives as a number, so `alarmSeverity === 3` is the right test.
- Measured poll rates shown in the expert views need a source (the T8 rate report or an asyn
  statistics record); none exists in the databases yet.
