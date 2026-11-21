# MIST-2 emulation: start, stop and test

Two emulated control computers of the MIST-2 ion source, with every device replaced by a
software simulator, and the new GUI on top. Everything runs in Docker inside WSL2.

- What was decided and why: [DESIGN.md](DESIGN.md)
- What is done, what is assumed, what is open: [STATUS.md](STATUS.md)
- Who built what: [PLAN.md](PLAN.md) and [briefs/](briefs/)

**Not verified:** these steps were run on one machine (WSL2, Ubuntu 22.04) on which Docker was
already installed. Section 1 was not tried on a fresh installation. Nothing here was run against
real hardware.

## 1. What the computer needs

| | Tested with |
|---|---|
| WSL2 with Ubuntu | 22.04 |
| Docker Engine, running inside WSL (not Docker Desktop) | 29.9.2 |
| Docker Compose plugin | 5.6.1 |
| `git`, `make`, `python3` with PyYAML | Ubuntu packages |
| `g++` | only for the simulator's check against the real libcom1 library |
| Free disk space | about 20 GB for the images |

Install Docker Engine and the Compose plugin as described at
<https://docs.docker.com/engine/install/ubuntu/>, and add your user to the group `docker`, so
that `docker ps` works without `sudo`. Nothing else is installed on the computer: EPICS, the
test tools and Node run in containers.

## 2. Get the code

```bash
git clone https://github.com/DanielWinklehner/rfq-dip-epics.git
cd rfq-dip-epics
git switch emulated-iocs
git submodule update --init
```

The submodule is React Automation Studio V8.1.0, needed for the GUI only. All commands below
are run from the repository root.

## 3. The emulated IOCs

| Command | What it does |
|---|---|
| `make -C emulation build` | Builds the images: EPICS base R7.0.10, asyn R4-46, StreamDevice 2.8.26, the IOC application, and the tools image. Takes several minutes the first time |
| `make -C emulation up` | Starts four containers and waits until both IOCs answer |
| `make -C emulation ca-proof` | Checks that both IOCs are reachable and that their logs have no error |
| `make -C emulation down` | Stops and removes everything, the plant model included |
| `make -C emulation restart` | Restarts the IOCs after an edit in `EPICS/Db` or `EPICS/ioc/iocBoot`. The simulators keep running, as the devices do when a control computer restarts. After a change of a simulator: `down`, then `up` |
| `make -C emulation logs` | Output of both IOCs |

| Container | Address | Role |
|---|---|---|
| `ioc-rack` | 172.30.0.11 | Rack IOC |
| `ioc-hv` | 172.30.0.12 | High-voltage platform IOC |
| `sim-rack` | 172.30.0.21 | Simulators of everything cabled to the rack computer |
| `sim-hv` | 172.30.0.22 | Simulators of the platform devices |
| `plant` | 172.30.0.30 | Plant model, only on request (section 6) |

If `172.30.0.0/24` collides with a network of yours: `export MIST2_SUBNET=172.31.5` before `up`.

**Read and write PVs** from the tools container, which has the EPICS command-line tools:

```bash
docker compose -f emulation/compose.yaml --profile tools run --rm tools caget TDK:voltage:read AIM:getpressure
```

```bash
docker compose -f emulation/compose.yaml --profile tools run --rm tools caput VALVE:s1:set 1
```

A Channel Access client of your own needs `EPICS_CA_AUTO_ADDR_LIST=NO` and
`EPICS_CA_ADDR_LIST=172.30.0.255`.

**IOC shell:** `docker attach mist2emu-ioc-rack-1`. Leave it with ctrl-p ctrl-q, not ctrl-c.

**Saved limits:** the current limits of the high-voltage supplies and of the filament discharge
supply are kept across `restart` and `down`/`up` in the Docker volume `mist2emu-save`. Their
defaults are in `EPICS/ioc/iocBoot/<ioc>/limits.defaults`. How to look at them and reset them:
[../../emulation/README.md](../../emulation/README.md), "Saved limits".

**Which PVs exist:** `RAS/mist2/ReactApp/src/registry/registry.json`, or the Word document in
`plan/out/`.

## 4. Tests

| Command | What it proves | Time |
|---|---|---|
| `make -C emulation test` | The whole system: clean start of both IOCs, every PV read, every set point written and followed, alarms on unacknowledged sets, every fault on every simulator with recovery, the interlock across both IOCs, the update rates against the bus arithmetic. Starts the emulation if needed | about 8 min |
| `make -C emulation test ARGS="-k valve"` | A part of it | |
| `emulation/devtest/run.sh emulation/devtest/<case>` | One device alone against its simulator. Cases: `matsusada`, `tdk`, `naim`, `mfc`, `faradaycup`, `turbo`, `libcom1_devices` | 10 s to 4 min |
| `emulation/sim/run_tests.sh` | The simulators without an IOC, and the libcom1 simulator against the real library | 1 min |
| `make -C emulation plan-check` | `plan/controls.yaml`, the databases and both `st.cmd` files agree | 10 s |

The system tests take devices and PV names from the registry. What each test module proves and
which time limits it uses: [../../emulation/tests/README.md](../../emulation/tests/README.md).

## 5. Make a device misbehave

Every simulator has a control port (its port plus 1000, see `emulation/sim/config/*.yaml`).
Example: the filament heating supply stops answering, and answers again.

```bash
docker compose -f emulation/compose.yaml --profile tools run --rm tools python3 -c "from mist2sim.control import ControlClient; print(ControlClient('sim-hv', 6001).fault('silent'))"
```

```bash
docker compose -f emulation/compose.yaml --profile tools run --rm tools python3 -c "from mist2sim.control import ControlClient; print(ControlClient('sim-hv', 6001).clear())"
```

Fault modes: `silent`, `close`, `garbage`, `slow`, and `trip` where the device has one. A fault
can be limited to one unit of a bus and to a time. All commands:
[../../emulation/sim/README.md](../../emulation/sim/README.md).

## 6. Plant model (optional)

Without it each simulator is on its own: a supply sees a fixed load, a gauge shows a constant.
With it the filament heating drives the discharge current with a thermal lag, gas flow and pumps
drive the pressures, and the extraction voltage drives the Faraday cup current.

| Command | What it does |
|---|---|
| `make -C emulation up-plant` | Starts the emulation with the plant model |
| `make -C emulation plant-stop` | Stops only the plant: every device goes back to its own behaviour |
| `make -C emulation plant-logs` | The plant's log |
| `python3 emulation/sim/tools/plant_step_response.py` | Gain, dead time and time constant of the model, for loop tuning |

Every number of the model is a property of the model. None is measured on MIST-2. The
parameters, each marked as law, estimate or free choice, are in
`emulation/sim/config/plant.yaml`. Run the system tests without the plant.

The turbopump needs about 70 s to reach its speed in the emulation (the real pump: about
9 minutes). Until then the pressure is too high for a discharge.

## 7. The GUI

| Command | What it does |
|---|---|
| `make -C RAS/mist2 dev-up` | Builds (about 15 minutes the first time) and starts the GUI in development mode |
| `make -C RAS/mist2 dev-down` | Stops it |
| `RAS/mist2/tools/pv-proof.sh` | Checks that the GUI's server reads a PV from each emulated IOC |

Open <http://localhost:3000/> in a browser on Windows. The GUI uses the ports 3000, 3001 and
9001 of the WSL machine. It finds the IOCs through `RAS/mist2/.env`, which is created from
`env.template` on first use.

**What you see:** an overview drawing of the source and the six-way cross, one tab per
subsystem (plasma, extraction, vacuum and gas, cooling and interlock, infrastructure), and
trends. A click on any element of a drawing opens that device in a browser window of its own,
which stays until you close it. Colour follows the EPICS alarm severity, and a record that is
INVALID shows that instead of a stale number. Expert information (PV names, alarm status, raw
values) is in each device window. There is no login. Only opening the vent valve asks first.

**Check it:** with the emulation and the GUI running, `RAS/mist2/tools/gui-check.sh` drives a
headless browser through every page and device window, compares what is shown with Channel
Access, injects faults and writes set points. It saves screenshots to
`RAS/mist2/tools/screenshots/`. It takes about 5 minutes.

Every device, PV name and state word in the GUI comes from the registry
(`RAS/mist2/ReactApp/src/registry/registry.json`, generated from `plan/controls.yaml`). How the
GUI is built: [../../RAS/mist2/README.md](../../RAS/mist2/README.md). Why it looks like this:
[gui/LAYOUT.md](gui/LAYOUT.md).

## 8. From the emulation to the real computers

The databases, the protocol files and `st.cmd` are the same. Only the port file differs:

```
EPICS/ioc/iocBoot/iocRack/st.cmd            the same for both
EPICS/ioc/iocBoot/iocRack/ports.sim.cmd     TCP ports of the simulators
EPICS/ioc/iocBoot/iocRack/ports.real.cmd    serial devices and Ethernet devices
```

On the real computer: build the top (`make -C EPICS/ioc`, local paths in
`EPICS/ioc/configure/RELEASE.local`) and start `EPICS/ioc/iocBoot/run-ioc.sh iocRack real`, or
`iocHV real` on the platform computer. An IOC that is started without a valid mode stops with
an error. It cannot come up on the wrong set of ports by accident.

Before that works, `ports.real.cmd` needs the real device names (the names under `/dev/mist2/`
are placeholders), and the assumptions in [STATUS.md](STATUS.md) need your answers.

## 9. Add or change a device

1. Database and protocol file in `EPICS/Db`, a simulator module in
   `emulation/sim/mist2sim/devices/` if the protocol is new, and a test case in
   `emulation/devtest/`.
2. One line per port in both port files, the `dbLoadRecords` line in `st.cmd`, and the simulator
   in `emulation/sim/config/rack.yaml` or `hv.yaml`.
3. The device in `plan/controls.yaml`: its database loads, and for a new database the roles of
   its records.
4. `make -C emulation plan-check`. It names everything that does not match yet.
5. `make -C emulation registry`. The GUI and the system tests pick the device up from there.

## 10. Where things are

| Path | Content |
|---|---|
| `EPICS/Db/` | Databases and protocol files, shared by emulation and reality |
| `EPICS/ioc/` | EPICS application and the startup files of both IOCs |
| `emulation/` | Images, Compose file, simulators, test cases, system tests |
| `emulation/sim/config/` | Which simulator stands behind which port, with all assumed values marked |
| `plan/` | `controls.yaml`, the single source of truth, and its generators |
| `RAS/mist2/` | The new GUI. `RAS/IsoDAR/` is the old one |
| `reference/lab-2023/` | The lab's files of 2023, read-only |
| `docs/emulation/` | This file, design, status, plan, briefs, GUI layout proposal |
