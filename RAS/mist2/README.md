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
| `roles.js` | what each registry role means: words, lamps, exponent format, trends |
| `alarm/` | the one rule for how an alarm state looks (`severity.js`), the shared store of alarm states, dots and chips |
| `components/fields/` | RAS `Widget` components: value, set point, request buttons, lamp, command, inline text |
| `components/devices/` | one widget per registry class, built from the device's roles |
| `synoptic/` | drawings: symbols, tags, layout; devices a drawing does not place are listed |
| `config/drawings.json` | the geometry of every drawing (edit numbers, not code) |
| `config/confirm.json` | requests that ask first (the vent valve) |
| `pages/` | main window, subsystem, trends, infrastructure pages, device window |

A device added to the registry appears on its page (listed beside the
drawing) and has its device window without a code change. No PV name is
written in the sources: `tools/gui-check.sh` checks that.

`tools/gui-check.sh` checks the GUI against the running emulation (pages,
values against Channel Access, a silent simulator, a stopped IOC, writes,
sources) with a headless browser and saves screenshots to `tools/screenshots/`.
It needs `make -C emulation up` and `make dev-up`, takes about ten minutes and
stops and starts the HV IOC container once.

`tools/pv-proof.sh` proves that pvServer delivers the test PVs of both IOCs,
`tools/pv-proof.sh --help` explains it. Where the code comes from and what was
removed from the boilerplate: [UPSTREAM.md](UPSTREAM.md).
