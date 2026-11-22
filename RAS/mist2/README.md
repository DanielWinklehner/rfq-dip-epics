# MIST-2 GUI (React Automation Studio V8.1.0)

Development stack, inside WSL2:

    git submodule update --init RAS/mist2/submodules/React-Automation-Studio
    make -C RAS/mist2 dev-up      # first build 20 to 30 minutes
    # open http://localhost:3000/ in the Windows browser
    make -C RAS/mist2 dev-logs
    make -C RAS/mist2 dev-down

Settings, including all Channel Access settings, are in `RAS/mist2/.env`
(created from `env.template`). Services, all on the host network:

| Service | Port | Purpose |
|---|---|---|
| `nginx` | tcp 3000 (all interfaces) | the URL the browser opens; routes `/socket.io` and `/api` to pvServer, everything else to Vite |
| `frontend` | tcp 3001 (127.0.0.1 only) | Vite development server, serves `ReactApp/src` and the RAS sources with hot reload |
| `pvserver` | tcp 9001 (all interfaces); Channel Access on ephemeral ports | Channel Access client, Socket.IO server for the browser |

## The GUI (`ReactApp/src/`)

Layout B of `docs/emulation/gui/LAYOUT.md` with the owner's change (G2): the
synoptic is the console, and a click on a device opens it in a browser window
of its own (`/device/<registry id>`, Controls, Trend, Expert). Main window tabs:
Overview, one per subsystem page of the registry, Trends, Infrastructure.

| Where | What |
|---|---|
| `registry/` | generated device registry (do not edit), read only through `registry.js` |
| `registry.js` | devices, roles, labels, state words, spare channels, flags, alarm records |
| `roles.js` | what each registry role means to the operator, and which are trended |
| `alarm/` | the one rule for how an alarm state looks (`severity.js`), the shared store of alarm states, dots and chips |
| `components/fields/` | value, lamp and inline text on the RAS socket hook (`useReading`), set point, request buttons and command as RAS `Widget` components; `format.js` formats every value |
| `components/Trend.jsx` | time-stamped trend on monitors (Plotly), used by the pages and the device windows |
| `components/devices/` | one widget per registry class, built from the device's roles |
| `synoptic/` | drawings: symbols, tags, layout; devices a drawing does not place are listed |
| `config/drawings.json` | the geometry of every drawing (edit numbers, not code) |
| `pages/` | main window, subsystem, trends, infrastructure pages, device window |

Every tag also sets, in place, what the operator sets in normal operation (owner,
2026-11-22): the set points and requests of its widget's operation group
(`synoptic/tagRows.js`), in the form of the device window's fields. Enter sends a
number, Escape or leaving the field gives it up; an unsent entry has a dashed
outline and ↵. A field whose record is INVALID still takes an entry (the IOC
accepts the write, and the record may be INVALID only because the device has not
answered since its start); without a connection it is disabled. Saved settings
stay in the device window.

Everything about the devices comes from the registry: names, labels, the words
of every state (valves closed/open, cup out/in, the supply status with
remote/local), which channels are spare (shown only in the device window), and
which request asks for confirmation (the vent valve). A device added to the
registry appears on its page (listed beside the drawing) and has its device
window without a code change. No PV name is written in the sources:
`tools/gui-check.sh` checks that.

A Matsusada supply (AU, REK) has a current limit, not a current set point: its
device window shows it under "Setting, saved by the IOC" beside the limit the
supply reports. The IOC saves a change and sends the limit with every switch-on.
The TDK keeps its current set point.

Nothing that shows a streaming value sets React state in an effect: the RAS
`Widget`/`PV` pair and RAS `GraphY` do, and with hundreds of them mounted React
reports "Maximum update depth exceeded". Read-backs therefore use the RAS
socket hook `useEpicsPV` directly, and trends are drawn by `Trend.jsx`; RAS
`Widget` is kept for the fields that write.

A trend line is drawn in steps and runs on to the present, since a monitor
sends a value only when it changes. It ends where its record turns INVALID or
the connection is lost, and starts again with the next valid value. A trend
without any valid value says so. A zoom stays until a double click.

Values are shown in the record's precision and unit. Units that span decades
(torr, mbar, Pa) are always in exponent format and trended on a log scale; an
SI unit (A, V, W, Hz, s) takes a prefix when a value is below 0.01 or from
10 000 on, and keeps the record's resolution up to three decimals
(999 nA, 1.000 µA, 15.234 kV).

`tools/gui-check.sh` checks the GUI against the running emulation (pages,
values against Channel Access, a silent simulator, a stopped IOC, writes,
sources, the latch of the interlock permit, the loop, values set in place) with a
headless browser and saves
screenshots to `tools/screenshots/`.
It needs `make -C emulation up` and `make dev-up`, takes about ten minutes and
stops and starts the HV IOC container once.

`tools/pv-proof.sh` proves that pvServer delivers the test PVs of both IOCs,
`tools/pv-proof.sh --help` explains it. Where the code comes from and what was
removed from the boilerplate: [UPSTREAM.md](UPSTREAM.md).
