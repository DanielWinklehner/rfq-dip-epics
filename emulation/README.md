# MIST-2 emulation

Two emulated control computers (Docker containers `ioc-rack` .11 and `ioc-hv` .12 on network
`mist2ctl`, `172.30.0.0/24`), each running one IOC from `EPICS/ioc`. Run from the repository root:

| Command | What it does |
|---|---|
| `make -C emulation build` | Build the images `mist2-ioc:dev` and `mist2-tools:dev` |
| `make -C emulation up` | Start both IOCs, wait until they are healthy |
| `make -C emulation down` | Stop and remove containers and network |
| `make -C emulation restart` | Restart the IOCs (after editing `EPICS/Db` or `EPICS/ioc/iocBoot`) |
| `make -C emulation ps` / `logs` | Container state / IOC output |
| `make -C emulation ca-proof` | Channel Access check from the network and from the WSL host |
| `make -C emulation devtest CASE=<dir>` | Test one device case (path relative to the repository root) |
| `make -C emulation plan` | `python plan/build.py`, writes `plan/out` |
| `make -C emulation plan-check` | The same into a temporary directory, fails on `WARNING` |
| `make -C emulation test` | System tests (`emulation/tests`) |

IOC shell: `docker attach mist2emu-ioc-rack-1` (leave with ctrl-p ctrl-q, not ctrl-c).
Channel Access clients: `EPICS_CA_AUTO_ADDR_LIST=NO EPICS_CA_ADDR_LIST=172.30.0.255`.
Another subnet: `export MIST2_SUBNET=172.31.5` before `up`.

Plant model (optional): without it each simulator has its own fixed model (a load resistance, constant pressures). With
it, filament, discharge, gas, vacuum, extraction and heat are coupled: raise the filament current
and the REK current follows, open the gas and the gauges rise. It is one more container (`plant`,
172.30.0.30, Compose profile `plant`) that talks only to the control ports of `sim-rack` and
`sim-hv`. Equations, parameters, disturbances and what it does not model: `sim/README.md`,
section "Plant model".

| Command | What it does |
|---|---|
| `make -C emulation up-plant` | Start the emulation with the plant model |
| `make -C emulation plant-stop` | Stop only the plant: every device goes back to its own behaviour |
| `make -C emulation plant-logs` | The plant's log (status every 10 s, events) |
| `make -C emulation down-plant` | Stop everything, the plant included (`down` does the same) |

`make -C emulation up` starts the emulation without the plant, exactly as before.
Disturbances for loop tests (emission drift, pressure burst): the plant's control port,
`172.30.0.30:6090`, see `sim/README.md`.

On a real Linux computer: `make -C EPICS/ioc` (local paths in `EPICS/ioc/configure/RELEASE.local`),
then `EPICS/ioc/iocBoot/run-ioc.sh iocRack real`.

Device tests: `emulation/devtest/run.sh <case> [pytest arguments]`. A case directory holds
`sim.yaml` (or a one-line `sim.cmd`), `ioc.cmd` and `test_*.py`; see the header of
`devtest/run.sh` and the example in `devtest/example/`. Logs go to `<case>/build/`.

## System tests

`make -C emulation test` runs the system tests of `emulation/tests/` against the full
emulation: it starts the emulation if it is not running (and stops it again afterwards; a running
one stays running), saves the IOC and simulator output to `emulation/build/<service>.log`, runs
pytest in the `tools` container, prints the update-rate table (`emulation/build/update-rate.md`)
and exits with pytest's exit code. Arguments go to pytest: `make -C emulation test ARGS="-k valve"`.
The suite takes about 8 minutes and leaves the system as it found it. What it proves, its time
limits and its expected failures: [tests/README.md](tests/README.md).
