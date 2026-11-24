# G1 design note: emulated IOCs and the new GUI

Status: **approved on 2026-11-21 (gate G1)**, D1 to D8 as proposed.
The decisions are marked **D1** to **D8** and collected at the end.

## 1. What changed since the prompt was written

`latest.zip` is a snapshot of the rack IOC from 2023 (now in `reference/lab-2023/`). It is newer
than the repository for the power supplies and the mass flow controller, and **its PV names
differ from the repository**. The names in the prompt (`thm:*`, `tdk:*`, `avr12:*`) come from
the repository's older `st.cmd`.

| Device | Repository (this branch) | Lab snapshot 2023 (and the lab GUI) |
|---|---|---|
| Device prefixes | `avr6`, `avr12`, `avr10`, `avr11`, `aim`, `thm`, `tdk` | `PRESSURE`, `VALVE`, `SENSOR`, `INTLK`, `AIM`, `THM`, `TDK`, `MFC` |
| AU and REK set points | `:voltage:set`, `:current:set` | `:voltage:setpoint`, `:current:setpoint` |
| AU and REK output | `:enable`, `:disable`, `:status:set`, `:reset` | `:SetToggleOutput`, `:ToggleOutput`, `:read_output_status` |
| TDK | `:voltage:set`, `:voltage:get`, `:status:set` | `:voltage:setpoint`, `:voltage:read`, `:status:setpoint` |
| nAIM | `aim:pressure:get` | `AIM:getpressure` |
| Interlock summary | `interlock_status` | `interlock_open` |
| MFC | no files | `MFC:getSP`, `MFC:setSP`, `MFC:getWink`, `MFC:setWink` |
| AU unit numbers | 1 source, 2 "Einzel lens" | 1 source, 2 puller, 3 lens 1, 4 lens 3 |

**D1. Proposal: the lab snapshot names are the baseline.** "Do not rename existing PVs" protects
the lab's clients, and the snapshot is the best record of what they use. The work of this branch
(acknowledged sets, identity records, alarm propagation) is kept and applied to those names.
Prefixes are `st.cmd` macros, so they cost nothing to change. The GUI and the tests take every
name from one generated registry, so the reconciliation with the real lab files next week is a
database edit plus one regeneration.

## 2. Emulation architecture

```
 Windows browser ──► RAS (own Compose project, host network, inside WSL2)
                          │ Channel Access, EPICS_CA_ADDR_LIST=172.30.0.255
        ┌─────────────────┴──────────── Docker network mist2ctl 172.30.0.0/24 ───────┐
        │  ioc-rack  .11                         ioc-hv  .12                         │
        │  st.cmd + ports.sim.cmd                st.cmd + ports.sim.cmd              │
        │      │ TCP                                 │ TCP                           │
        │  sim-rack  .21                         sim-hv  .22          plant .30      │
        │  one simulator process per bus/device  (same)               (step 2)       │
        │                                        loop  .40  (Channel Access client   │
        │                                        of ioc-hv: the PID, since rev 0.11) │
        └────────────────────────────────────────────────────────────────────────────┘
```

- **Docker Compose in WSL2, one container per emulated computer**, as preferred. Docker 29.9 and
  Compose 5.6 are already installed in WSL as a native engine, so host networking for RAS works.
- **The Channel Access trap does not arise**: each IOC has its own network namespace and IP
  address, so each one receives unicast and broadcast searches. Clients use the subnet broadcast
  address. The first task proves this from a second container and from the WSL host before
  anything is built on it.
- **Simulators run in their own containers** (`sim-rack`, `sim-hv`), not inside the IOC
  containers. The IOC image then holds exactly what the real IOC holds, `docker pause sim-hv`
  unplugs a whole platform, and Ethernet devices (Optas) are separate hosts as in reality.
- **The loop service** (`loops/mist2loop`, added 2026-11-22) is one more container, `loop`. On
  the real platform computer it runs beside the IOC. Its records are in `ioc-hv`
  (`docs/emulation/LOOP.md`).
- **The data logger** (`logger/`, added 2026-11-22) is not part of the emulation's Compose
  project: database, logger and Grafana are a project of their own on the host network, and the
  logger is a Channel Access client like the GUI. Its state records are in `ioc-rack`
  (`docs/emulation/LOGGER.md`).
- **One image for both IOCs**: EPICS base 7, asyn, unmodified StreamDevice, and one IOC
  application built from a new EPICS top in `EPICS/ioc/`. `EPICS/Db` is mounted into the
  containers, so a database edit needs an IOC restart, not an image build.

### Same files for real and emulated

```
EPICS/Db/                         databases and protocol files, shared
EPICS/ioc/iocBoot/iocRack/st.cmd  loads ports.$(MIST2_PORTS).cmd, then the databases
                  ports.sim.cmd   drvAsynIPPortConfigure("mat_co", "sim-rack:5003") ...
                  ports.real.cmd  drvAsynSerialPortConfigure("mat_co", "/dev/mist2/co-u32") + baud ...
EPICS/ioc/iocBoot/iocHV/          the same three files for the platform IOC
```

The port files contain port configuration and nothing else. Unit numbers, full scales and
prefixes are in `st.cmd`. The existing `EPICS/st.cmd` stays untouched as the historical record.
Linux device names in `ports.real.cmd` are placeholders until the udev rules exist.

### Simulators (`emulation/sim/mist2sim`, Python, standard library only)

- **Core**, shared by all: TCP server per bus, one transaction at a time. Each reply is held
  back by `(request + reply characters) x 10 bits / baud + turnaround`. Signals follow their
  set point with a time constant and carry noise.
- **One small module per protocol**: `libcom1`, `matsusada_co` (several units per bus),
  `tdk_genesys`, `edwards_naim`, `mks_rs485` (multi-drop), `nt20_monitor` (talks only).
- **One control interface** on a second TCP port per simulator, JSON lines:
  `fault` (silent, close, garbage, trip, per bus or per unit, optionally timed), `get`, `set`,
  `stats` (transaction counts, used for the update-rate report).
- **Plant model later without rewriting**: every simulator exposes its actuators and process
  values as named signals on the control interface. The plant is one more client that reads
  actuators and writes process values. Without it, each device uses its own simple model.
- **libcom1 fidelity**: the Python engine replays `AVR/libcom1/tests/script.hpp` and its output
  is diffed against `replay_host` built from the real library, for both number formats
  (AVR `dtostre` and `%g` as on the Opta).

### Bus arithmetic for the AU supplies (from the CO series manual, rev 0.4)

| Transaction | Characters | Time at 9600 baud |
|---|---|---|
| `#1 MN1` → `MONI1=FFFH` | 7 + 11 | 18.8 ms |
| `#1 CH0?` → `CH0=FFFFH` | 8 + 10 | 18.8 ms |
| `#1 STS` → `#1 CO RM` | 7 + 9 | 16.7 ms |

With two polled supplies per chain, monitors fast, status at 1 Hz and set-point echoes every 5 s,
one monitor PV updates at about **9.9 Hz with 5 ms turnaround** and **6.5 Hz with 16 ms** (the
default latency timer of FTDI-type USB adapters). Today's database on one chain of five supplies
gives about 1.7 Hz at 5 ms turnaround. The turnaround time of the real adapters is not known: it is a simulator
setting, and the test reports measured against predicted rate for the value in use.

Two facts from the manual that shape the database:

- **Set commands are not answered.** A CO set cannot end in an "ack missing" alarm. Instead each
  set triggers a read of the set-point echo, and a silent supply turns that record INVALID.
- **`#AL` is valid for `CH0`, `CH1`, `SW`, `RST`, `REN`** and others, so "all off" is `#AL SW0`
  once per chain.

## 3. Devices: what is emulated and under which names

Existing names are kept as in section 1. New records are marked **new**.

| IOC | Device | Port | PVs |
|---|---|---|---|
| platform | Thermocouples | `thermo` | `THM:t1:get` … `t4`, `THM:id/firmware/channels`. **new**: `THM:j<n>:get` (junction), `THM:f<n>:get` (fault code with alarm). The board sends 16 channels, the database uses 4 |
| platform | TDK GENESYS 8-300 | `TDK` | `TDK:voltage:setpoint`, `:voltage:read`, `:current:setpoint`, `:current:read`, `:status:setpoint`, `:status:get`. **new** (from the plan): `TDK:power:get`, `TDK:mode:get`, `TDK:fault:get` |
| platform | REK150-24 | `REK` | `REK-1:*` as in the snapshot. Full-scale macros `VFS=150`, `IFS=24` (55 later). Unit of the current fixed from mA to A |
| rack | AU x 5 | `mat_opt`, `mat_co` | `AU-20P7-<unit>:*` as in the snapshot, reworked polling; the source supply (unit 1) `AU-20P15-1:*`, the lab's name in its files of 2026-11-24 (T26). **new**: `AU:alloff:set` |
| rack | MKS GV50A | `MFC` | `MFC:getSP`, `MFC:setSP`, `MFC:getWink`, `MFC:setWink`. **new**: `MFC:getFlow` |
| rack | Valve box | `AVR12` | `VALVE:s1:get` … `s8`, `VALVE:s1:set` … `s8`, `VALVE:id/firmware/channels` |
| rack | Gauge controller | `AVR6` | `PRESSURE:apg:getpressure`, `PRESSURE:diag_box:getpressure`, `PRESSURE:id/...` |
| rack | nAIM | `AIM` | `AIM:getpressure`, `AIM:enable` |
| rack | Faraday cup Opta | `AVR16` | `FC1:data`, `FC1:i1:getcurrent`, `FC1:i2:getcurrent`, the lab's names in its files of 2026-11-24 (T26; until then the assumed `FC:current:get` over TCP). No identity records: protocol 1 |
| rack | Flow meter Opta | `AVR23` | `FLOW:data`, `FLOW:f1:getflow` … `f5` (l/min), the lab's names of 2026-11-24 (T26). No identity records: protocol 1 |
| rack | NT 20 x 2 | `TURBO`, `NT20_1`, `NT20_2` | **new**, see section 4 |
| rack | Sensor box | `AVR10` | `SENSOR:t<n>:gettemp`, `SENSOR:f<n>:getflow` (see D5). No longer loaded since T26: the flow meter Opta replaces it, as in the lab's `st.cmd` of 2026 |
| rack | Old interlock box | `AVR11` | `INTLK:i1:get_interlock`, `INTLK:i2:get_interlock`, `interlock_open` (see D5) |

**D2. AU units and chains.** Units 1 to 4 as in the 2023 `st.cmd`, the new lens 2 supply as
unit 5. Unit numbers stay unique across both chains, because the PV name is built from them.

| Unit | Role | Model | Full scale | Chain |
|---|---|---|---|---|
| 1 | Ion source | AU20P15 | 20 kV, 15 mA | USB-OPT (`mat_opt`) |
| 2 | Puller | AU20N7.5 | 20 kV, 7.5 mA | USB-OPT (`mat_opt`) |
| 3 | Lens 1 | AU20P7.5 | 20 kV, 7.5 mA | CO-U32 (`mat_co`) |
| 5 | Lens 2 | AU20N7.5 | 20 kV, 7.5 mA | CO-U32 (`mat_co`) |
| 4 | Lens 3, not polled | AU20P7.5 | 20 kV, 7.5 mA | CO-U32 (`mat_co`) |

Lens 3 has its records loaded with scanning switched off by a macro. The simulator answers for
it, so the rate test can show what polling it would cost.

**D3. Sign of the negative supplies.** Macros `VFS`, `IFS` and `POL`. `POL` defaults to
positive numbers for every supply, which is what the snapshot does. Showing the puller and
lens 2 with a minus sign is then one macro per supply. I leave it positive unless you say
otherwise, because it changes what existing PVs mean.

**AU and REK output switching.** The snapshot routes the on/off request through a `calcout`
that reads `interlock_open` and forces the output off while the interlock is open. I keep that
chain and its PV names and make the permit PV a macro (`PERMIT=interlock_open`). When the new
interlock system arrives, only the macro changes.

**Devices on placeholders until the lab files arrive.**

- **MFC**: the snapshot's files were commented out in its `st.cmd` and are a draft (set point
  only, no flow read-back). I complete them from the MKS RS-485 manual. Address 254 and
  9600 baud come from the snapshot.
- **Faraday cup Opta**: assumed libcom1 over TCP with one current channel. The cup actuator is
  assumed to be valve channel `VALVE:s4`, as labelled in the lab GUI. (Settled by the lab's
  files of 2026-11-24, T26: `FC1`, two values, libcom1 protocol 1 on a USB serial line.)
- **nAIM**: the snapshot's `enable` sends `!C752 0|1` and does not read the reply. I add the
  reply from the Edwards manual, so that a missing answer raises an alarm.

Not in the CO command set, so not built: `REK-1:mode:read` and `REK-1:alarm:read` from the plan.
`STS` reports only output on/off and remote/local.

## 4. Leybold NT 20 (checked against GA 05.208/8, 01/97)

Your proposal holds. The instructions confirm it and add two details.

| Topic | Operating instructions | Consequence |
|---|---|---|
| Remote inputs | Floating inputs REMOTE, START, STOP, HEATING on the rear terminal strip. Active 13 to 33 V. START is high-active, **STOP is low-active and dominant**. Pulses longer than 200 ms | Start and stop need no supply: the unit offers +15 V and GND on terminals 10 and 9 |
| One contact per pump | Fig. 6, "passive control via ON/OFF switch" | One Opta relay per pump: closed = run, open = stop |
| Status relays | **Three**, not two: NORMAL (speed above 80 % of target), ACCEL, FAILURE (changeover). 250 V AC 3 A, 50 V DC 2 A | Three Opta inputs per pump |
| Failure reset | "with the STOP command (key or remote control)" | No reset PV: writing stop resets |
| Failure relay | Open at power off, closes on failure | A dead controller does not look failed. The state PV uses all three relays |
| RS-232 | "Interface for data output", 25-pin D female, 9600 baud, all main parameters every 8 s, "more details on request" | Output only, format unpublished, as you expected |

**One Opta serves both pumps**: 2 of 4 relays and 6 of 8 inputs. The two spare relays could
switch HEATING if the pumps have flange heaters.

| PV | Type | Source |
|---|---|---|
| `TURBO1:start:set` | bo | Opta relay: 1 = run, 0 = stop and failure reset |
| `TURBO1:start:get` | bi | Relay state read back |
| `TURBO1:atspeed:get` | bi | NORMAL relay |
| `TURBO1:accel:get` | bi | ACCEL relay (added to the plan's list) |
| `TURBO1:failure:get` | bi | FAILURE relay, MAJOR alarm |
| `TURBO1:state:get` | mbbi | Stopped, accelerating, normal, failure, inconsistent (added) |
| `TURBO1:raw:get` | text | Last RS-232 record, unparsed (added) |
| `TURBO1:age:get` | ai, s | Age of the last record, alarm above 20 s |
| `TURBO1:speed:get`, `:current:get` | ai | Parsed from the record |
| `TURBO:id`, `:firmware`, `:channels` | | The Opta itself |

`TURBO2:*` is the same. The RS-232 parser is one protocol file and one database, loaded per
pump by one `st.cmd` line. Until you capture real output, simulator and parser share an
**invented** record format, labelled as such in both files. `raw` and `age` work with any format.

## 5. The RAS application

- **D6. It lives in this repository**, in `RAS/mist2/`, created from
  `React-Automation-Studio-Example-Project-1` with RAS V8.1.0 as a git submodule. Reason: the
  registry is generated from `plan/controls.yaml` and the databases, so a PV change and its GUI
  change are one commit. `RAS/IsoDAR` stays until the new GUI is accepted.
- The lab GUI in `latest.zip` is newer than `RAS/IsoDAR` (10 of 25 files differ). It is the
  reference for the look until you bring the current one.
- RAS runs as its own Compose project with host networking inside WSL2. Before any page is
  built, its pvServer must read one PV from each emulated IOC.
- The layout options come at G2.

## 6. Decisions

| | Question | My proposal |
|---|---|---|
| D1 | Which PV names are "existing"? | The 2023 lab snapshot, reconciled with the real lab files next week |
| D2 | AU units and chains | Table in section 3 |
| D3 | Negative supplies with a minus sign? | No, positive as today, switchable by macro |
| D4 | Names of the new PVs | Upper-case device prefix as in the lab (`TURBO1`, `FC`, `MFC`), tables above |
| D5 | Sensor box and old interlock box in the emulator? | Yes. Both are in the 2023 `st.cmd`, cost nothing extra, and give the cooling page and the output gate something to read. (Since T26 the sensor box is out: the lab's `st.cmd` of 2026 loads the flow meter Opta in its place.) |
| D6 | Where the GUI lives | This repository, `RAS/mist2/` |
| D7 | NT 20 interface | One Opta for both pumps, RS-232 listen-only, section 4 |
| D8 | Keep `plan/out/` (10 MB, regenerated by every build) under version control? | Keep the PDFs and the Word file, drop PNG and SVG |
