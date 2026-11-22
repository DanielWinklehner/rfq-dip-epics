# MIST-2 data logger

A Channel Access logger of our own (`mist2log`, Python with pyepics and psycopg) that records the
PVs of the plan in TimescaleDB, with Grafana to look at the data. Design, data model, the tier of
each PV group, sizing and backup: [docs/emulation/LOGGER.md](../docs/emulation/LOGGER.md).

| Command (from the repository root) | What it does |
|---|---|
| `make -C logger up` | Builds the logger's image if needed, writes the Grafana dashboards from the registry, starts database, logger and Grafana. Works whether or not the IOCs run |
| `make -C logger down` | Stops and removes the containers. The data stays in the volumes `mist2log-data` (database) and `mist2log-grafana` |
| `make -C logger logs` | Follows the logs |
| `make -C logger restart` | After `make -C emulation registry`: the logger reads the new PV list, the dashboards are written again |
| `make -C logger test` | The tests (below). Starts the emulation and the logger if they do not run, stops what it started. About 9 minutes |
| `make -C logger read ARGS="TDK:current:read --last 10m"` | The reading tool, CSV on standard output |

Settings: `logger/.env`, created from `env.template` on the first `make`: database passwords,
Channel Access addresses, ports (bound to 127.0.0.1 unless `MIST2LOG_BIND` opens them), buffer
size. Grafana: <http://localhost:3300/> (anonymous viewers; `admin` with `GRAFANA_ADMIN_PASSWORD`).
The database: `127.0.0.1:5434`, database `mist2log`, users `mist2log` (the logger) and
`mist2log_reader` (read only: Grafana, the reading tool).

## Files

| Path | What it is |
|---|---|
| `mist2log/config.py` | Settings from the environment; the PV list from the registry (`log` of each PV) |
| `mist2log/core.py` | The rules: rows, intervals (mean, minimum, maximum weighted by time), events, time stamps, gaps. No Channel Access, no database |
| `mist2log/store.py` | Schema, life times, the writer thread with its bounded buffer |
| `mist2log/service.py` | Channel Access monitors, the tick once a second, the state records `LOGGER:*` |
| `mist2log/schema.sql` | Tables and the reading functions (`log_read`, `log_trend`) |
| `mist2log/read.py` | Module and command line tool for reading (`python -m mist2log.read --help`) |
| `mist2log/dashboards.py` | Writes the dashboards from the registry (standard library) |
| `grafana/provisioning/` | Data source and dashboard provider of Grafana |
| `tests/` | `test_core.py` (the rules alone), `test_system.py` (against the emulation), `run.sh` |

## Tests

`make -C logger test` runs `tests/run.sh`: the unit tests of the rules, then the system tests
against the emulation in the order of `tests/test_system.py`. The tests stop and start an IOC,
the database and the logger through `run.sh` (the test container has no Docker), and leave
everything as they found it, the saved settings (`limits.sav`) of the IOCs included. On a shared
machine run it under the emulation's lock: `flock /tmp/mist2emu.lock make -C logger test`.
The load table of the run is printed and saved in `logger/build/load.md`.

## On a real computer

The same Compose project. In `.env`: real passwords, `EPICS_CA_ADDR_LIST` with the broadcast
address of the control network (or the two IOC computers), and `MIST2LOG_REGISTRY_FILE` if the
repository is elsewhere. The logger runs on the host network, as any Channel Access client of
that computer. Where it runs is open (`plan/controls.yaml`, software questions).
