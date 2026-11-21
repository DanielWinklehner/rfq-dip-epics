You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T12: a simple plant model behind the device simulators. A lead engineer wrote this brief, will run your acceptance test himself, and will merge your branch. Other engineers work in parallel on other files, so stay inside the files you own.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t12`, on branch `emu/t12-plant-model`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never edit, stage or commit anything in `/home/daniel/code/rfq-dip-epics` outside your worktree. Check that `git -C /home/daniel/code/rfq-dip-epics/.claude/worktrees/t12 branch --show-current` prints `emu/t12-plant-model`. If not, stop and report.
- Commit on that branch only. Small commits with clear messages. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Host Python is 3.10 with PyYAML. Docker works without sudo.
- **Do not start the full emulation** (`make -C emulation up`): it uses fixed names and the fixed network 172.30.0.0/24, and another engineer is running the system test suite on it right now. Develop and test with the simulators started in-process (`SimThread`, see the simulator README), which needs no Docker. The lead checks the plant on the full emulation himself after merging.

# Read first
1. `docs/emulation/DESIGN.md` section 2, part "Simulators": the plant model was planned from the start as one more client of the simulators' control interface.
2. `emulation/sim/README.md`: the simulator core, signals (`set` puts a signal under outside control, `release` gives it back), `ControlClient`, `SimThread`.
3. `emulation/sim/config/rack.yaml` and `hv.yaml`: every simulator of the emulation, with the signals a plant can read and drive. The device modules in `emulation/sim/mist2sim/devices/` say what each signal means: `tdk_genesys.py` (programmed and measured voltage and current, `load_ohm`), `matsusada_co.py` (per unit `vset`, `iset`, `vout`, `iout`, `output`, `load_ohm`), `mks_rs485.py` (set point and flow), `edwards_naim.py` (pressure, on), `nt20_monitor.py` (run, speed, normal), `libcom1.py` (one signal per channel: gauges p1 and p2, thermocouples, sensor box temperatures and flows, valve relays, Faraday cup current).
4. `plan/controls.yaml`: the machine. In `software.loops` the owner describes the first control loop: the discharge current (measured by the filament discharge supply) is regulated through the filament heating current, on a time scale of about a second, "which matches a thermal filament". The plant model is the test bed for that loop.

# Background
MIST-2 is a filament-driven multicusp ion source. A tungsten filament is heated by the TDK supply (8 V, 300 A). The REK supply (150 V, 24 A) holds the discharge voltage between filament and chamber, and the discharge current it delivers depends on the electron emission of the filament, on the gas pressure in the chamber and on the discharge voltage. Hydrogen comes in through a mass flow controller and a shutoff valve. Two turbopumps on a common foreline pump the source and the diagnostic box. The ions are extracted by the source voltage (up to 20 kV) against a puller electrode, pass electrostatic lenses, and hit a Faraday cup when it is moved in.

Today every simulator is an island: the discharge current follows a fixed load resistance, the pressures are constants with noise. The plant model connects them, so that a control loop, a GUI trend or a start-up sequence sees a machine that reacts.

# Goal
A separate process that reads the actuators from the simulators and writes the process values back, a few times per second, through the public control interface only. No change to any simulator module and none to the core. If you find that the control interface lacks something the plant needs, describe the smallest change and work around it.

# What the model must do (keep each relation as simple as it can be and still have the right sign, the right order of magnitude and a plausible time constant)
1. **Filament**: electrical power heats it with a thermal lag of about a second. Its resistance rises with temperature, so the TDK sees a load that changes (drive the TDK simulator's load resistance). Electron emission rises steeply with temperature (Richardson's law or a fitted exponential).
2. **Discharge**: the discharge current is limited by emission at low filament power and by voltage and pressure otherwise, with a smooth transition. No discharge below a minimum discharge voltage or without gas. The REK simulator must then show that current at its voltage (drive its load resistance), and its own current limit must still work.
3. **Gas and vacuum**: the source pressure follows the gas flow and the pumping speed with a short time constant. Shutoff valve closed means no flow into the source whatever the controller reports. A turbopump that is not at normal speed pumps much less. The foreline pressure follows the gas load and the foreline valve. The vent valve open brings the pressure up fast. Map the three gauge readings (source ion gauge, diagnostic box gauge, foreline gauge) from these.
4. **Extraction**: with source and puller voltage on, a beam current proportional to the discharge current, rising with extraction voltage and saturating. The source supply delivers that current plus a small leakage (drive its load). The Faraday cup reads the beam current when it is in (valve channel 4), and nothing when it is out.
5. **Heat**: the thermocouple temperatures on the source rise with filament and discharge power, and the cooling water temperatures of the sensor box follow with a longer time constant. Time constants here are minutes in reality: make them configurable and choose defaults that show an effect within a minute at a desk, and say so.
- Every coefficient and time constant is a named parameter in one configuration file, with unit and a comment that says where the number comes from: a physical law, an order-of-magnitude estimate (say so), or a free choice. Nothing about the real MIST-2 is known beyond the supply ratings and what is in `plan/controls.yaml`: do not present an estimate as a measured property of the machine.
- The model is a pure, deterministic step function (state, inputs, dt) -> (state, outputs), separate from the code that talks to the simulators, so that it can be tested without sockets and reused by a control-loop developer in a notebook.

# The process around it
- `python -m mist2sim.plant --config <plant.yaml>`: connects to the control ports of the simulators it needs (hosts and ports from its configuration), runs at a fixed rate (default 10 Hz), logs one line per second at most.
- It tolerates a simulator that is not there yet, or goes away and comes back: it keeps trying, and the rest of the model keeps running on the last known value, clearly logged.
- On exit (SIGTERM, SIGINT) it releases every signal it has taken, so that each device goes back to its own behaviour.
- It exposes its own state through the same kind of control port as a simulator (`get`: filament temperature, emission, pressures, beam current; `set`: a few disturbances for loop tests, at least a drift of the emission and a pressure burst), so that a test can watch and disturb it.

# Files you own
- `emulation/sim/mist2sim/plant/` (new package), `emulation/sim/tests/test_plant*.py`
- `emulation/sim/config/plant.yaml`
- `emulation/sim/tools/plant_step_response.py` (see below)
- `emulation/compose.yaml`: only a new service `plant` (address .30 on the network `mist2ctl`, image `mist2-tools:dev`, started only with the Compose profile `plant`, so that the emulation without the profile behaves exactly as today)
- `emulation/Makefile`: only new targets for the plant (start the emulation with and without it)
- `emulation/sim/README.md` and `emulation/README.md`: only a new section on the plant
Nothing else. Another engineer is adding a `test` target to `emulation/Makefile` and a test section to `emulation/README.md` at the same time: keep your additions in separate blocks so that the two merge cleanly.

# Deliverables
1. The model, the process, the configuration and the Compose service as above.
2. Tests, all running without Docker, as part of `emulation/sim/run_tests.sh` (they are picked up by the unit test discovery):
   - the pure model: each relation has the right sign and limit cases (no gas no discharge, cold filament no emission, valve closed no flow, pump stopped pressure up, cup out no cup current), energy and current never negative, a steady state exists for sensible inputs, and a step in filament current gives a discharge current that settles with the configured lag;
   - the process with the real simulators in-process (`SimThread` with the two configuration files of the emulation, on free ports): through the DEVICE protocols or the control interface, set the TDK current, the REK voltage, the gas flow, open the valves, start the pumps (make them fast through their settings), and see the discharge current, the pressures, the beam current on the Faraday cup and a temperature respond; stop the plant and see every device back on its own behaviour; stop and restart one simulator while the plant runs.
3. `emulation/sim/tools/plant_step_response.py`: runs the pure model, applies a step of the filament heating current around a working point, and prints what a loop designer needs: steady-state gain (A of discharge current per A of filament current) at three working points, dead time and time constant, and the same for a gas flow step on the source pressure. This is the document the first control loop will be tuned from, so make its output readable and say in it which numbers are properties of the MODEL.
4. A section in `emulation/sim/README.md`: the equations in plain text, the parameter table, how to start the plant with the emulation, how to disturb it, and what it does NOT model.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    emulation/sim/run_tests.sh
    python3 emulation/sim/tools/plant_step_response.py

Both exit 0. Afterwards the lead starts the emulation with the plant (`make -C emulation` with the target you name), raises the filament current and the discharge voltage from Channel Access, and expects the discharge current PV, the pressure PVs and the Faraday cup PV to respond, and everything to return to today's behaviour when the plant is stopped.

# Rules
- Simple first. A model that a physicist can read in ten minutes and correct is worth more than a detailed one.
- Do not invent facts about the machine.
- Leave no process and no container running when you finish.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t12-plant-model @ <commit>
    BUILT: one line per part
    EQUATIONS: the model in a few lines
    PARAMETERS: name, default, unit, source (law, estimate, free choice)
    SIGNALS: which simulator signals the plant reads and which it drives
    STEP RESPONSE: the output of the tool
    VERIFIED: the acceptance commands with exit code and key output
    HOW TO RUN: the commands for the lead's check on the full emulation
    DECISIONS: choices the brief left open, each with one reason
    NEEDS THE LEAD: changes outside your files, open questions
