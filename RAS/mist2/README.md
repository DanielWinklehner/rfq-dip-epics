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
| `components/fields/` | RAS `Widget` components: value, set point, request buttons, lamp, command, inline text; `format.js` formats every value |
| `components/devices/` | one widget per registry class, built from the device's roles |
| `synoptic/` | drawings: symbols, tags, layout; devices a drawing does not place are listed |
| `config/drawings.json` | the geometry of every drawing (edit numbers, not code) |
| `pages/` | main window, subsystem, trends, infrastructure pages, device window |

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

Values are shown in the record's precision and unit. Units that span decades
(torr, mbar, Pa) are always in exponent format and trended on a log scale; an
SI unit (A, V, W, Hz, s) takes a prefix when a value is below 0.01 or from
10 000 on (1.00 µA, 20.0 kV).

`tools/gui-check.sh` checks the GUI against the running emulation (pages,
values against Channel Access, a silent simulator, a stopped IOC, writes,
sources, the latch of the interlock permit) with a headless browser and saves
screenshots to `tools/screenshots/`.
It needs `make -C emulation up` and `make dev-up`, takes about ten minutes and
stops and starts the HV IOC container once.

`tools/pv-proof.sh` proves that pvServer delivers the test PVs of both IOCs,
`tools/pv-proof.sh --help` explains it. Where the code comes from and what was
removed from the boilerplate: [UPSTREAM.md](UPSTREAM.md).
