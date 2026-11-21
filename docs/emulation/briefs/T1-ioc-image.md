You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T1. A lead engineer wrote this brief, will run your acceptance test himself, and will merge your branch. Other engineers work in parallel on other files, so stay inside the files you own.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t1`, on branch `emu/t1-ioc-image`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. `/home/daniel/code/rfq-dip-epics` itself is the lead's worktree: never edit, stage or commit anything there. Check that `git -C /home/daniel/code/rfq-dip-epics/.claude/worktrees/t1 branch --show-current` prints `emu/t1-ioc-image` and that `docs/emulation/DESIGN.md` exists in your worktree. If not, stop and report.
- Commit on that branch only. Small commits with clear messages. Never commit on `master` or `emulated-iocs`. Never push, never open a pull request.
- Read first: `docs/emulation/DESIGN.md` (the approved design, section 2 is yours), `docs/emulation/PLAN.md`, `EPICS/README`, `EPICS/st.cmd` (old Windows startup file, a historical record, do not edit it), `EPICS/Db/libcom1.proto`.
- Host: WSL2 Ubuntu 22.04, 28 cores. `sudo` needs a password, so install nothing on the host. Docker 29.9 and Docker Compose 5.6 work without sudo. Host Python is 3.10 with PyYAML and without pytest. Everything else goes into containers.

# Goal
Two emulated control computers as Docker containers, each running one EPICS IOC, each with its own IP address, built from one image. Plus the harness that other engineers will use to test one device database against one device simulator. No devices yet: you build the foundation.

# Files you own (create them, nobody else touches them)
- `emulation/docker/` (Dockerfiles), `emulation/compose.yaml`, `emulation/Makefile`, `emulation/README.md`, `emulation/tools/`, `emulation/devtest/`
- `EPICS/ioc/` (a new EPICS application top)
- `EPICS/Db/ioc_info.db`
Do NOT create or edit anything under `emulation/sim/` (another engineer builds the Python simulator package `mist2sim` there, in parallel) and do not edit other files in `EPICS/Db`, `EPICS/st.cmd`, `EPICS/Makefile`, `plan/`, `RAS/`, `docs/`. If you need a change outside your files, describe it in your report.

# Deliverables

## 1. Image `mist2-ioc:dev` (`emulation/docker/ioc.Dockerfile`, build context = repository root)
- EPICS base 7.0.x, asyn, StreamDevice, all built from source at pinned release tags (find the latest stable tags with `git ls-remote --tags`, pin them as build arguments, report them). StreamDevice must be UNMODIFIED: the databases need no custom converter.
- Then the IOC application from `EPICS/ioc` (see 2). The image contains the repository's `EPICS/` tree at `/opt/mist2/EPICS`, so the layout inside the image equals the layout in the repository.
- `caget`, `caput`, `camonitor`, `cainfo` on the PATH.

## 2. EPICS top `EPICS/ioc/`
- Standard layout: `configure/`, `mist2App/src/` (one binary `mist2` with base, asyn including drvAsynIPPort, drvAsynSerialPort and asynRecord, and StreamDevice), `iocBoot/iocRack/`, `iocBoot/iocHV/`.
- The databases are NOT installed by the build. Startup files load them directly from `EPICS/Db` through one variable (`MIST2_DB`, which resolves to `<top>/../Db`), and `STREAM_PROTOCOL_PATH` points there too.
- Each IOC has exactly three files: `st.cmd`, `ports.sim.cmd`, `ports.real.cmd`.
  - `st.cmd` is THE SAME for emulation and for the real computer. It loads `ports.<mode>.cmd`, where mode comes from the environment variable `MIST2_PORTS` (`sim` or `real`). If `MIST2_PORTS` is unset or the file is missing, the IOC must fail visibly and not start half-configured. Find out which iocsh mechanism does this reliably (`iocshLoad`, `<` with a macro, or a check in the launch script) and say which you chose and why.
  - The port files contain asyn port configuration and nothing else. At this stage they hold only a header comment and one commented example each: `drvAsynIPPortConfigure("TDK","sim-hv:5001")` in the sim file, and `drvAsynSerialPortConfigure("TDK","/dev/mist2/tdk")` plus the `asynSetOption` lines for 19200 8N1 in the real file.
  - `st.cmd` has a clearly marked section `## Devices` that stays empty except for one commented example line. The lead fills it in later. Do not add device lines.
  - `st.cmd` loads `EPICS/Db/ioc_info.db` with `P=IOC-RACK` or `P=IOC-HV`.
- `EPICS/Db/ioc_info.db`: `$(P):heartbeat` (counts up once per second) and `$(P):mode` (a string record that shows the value of `MIST2_PORTS`, using the `getenv` device support of EPICS 7, so that a GUI can show "sim" or "real").
- One launch script, used by the container entrypoint AND usable on a real Linux host built from the same top: `EPICS/ioc/iocBoot/run-ioc.sh <iocRack|iocHV> <sim|real>`. `st.cmd` must not depend on a generated `envPaths` file that a bind mount would hide (see 3).
- Make the IOC shell usable in a container (`docker attach` or `docker exec`), and make sure the IOC does not exit when stdin is not a terminal.

## 3. `emulation/compose.yaml`
- Project name `mist2emu`. One user-defined bridge network `mist2ctl` with subnet `${MIST2_SUBNET:-172.30.0}.0/24`.
- Services `ioc-rack` (address .11) and `ioc-hv` (address .12), both from `mist2-ioc:dev`, `MIST2_PORTS=sim`.
- Bind-mount the repository's `EPICS/Db` and `EPICS/ioc/iocBoot` read-only over the copies in the image, so that a database or startup file edit needs only `docker compose restart`, not an image build.
- Health check per IOC (its heartbeat PV answers).
- A `tools` service under the Compose profile `tools`, image `mist2-tools:dev` (`emulation/docker/tools.Dockerfile`, FROM `mist2-ioc:dev`): Python 3 with pytest, pyepics, PyYAML, python-docx, pillow, plus Graphviz (`dot`) and poppler-utils (`pdfunite`). Repository mounted at `/repo`, working directory `/repo`, `PYTHONPATH=/repo/emulation/sim`, `EPICS_CA_AUTO_ADDR_LIST=NO`, `EPICS_CA_ADDR_LIST=${MIST2_SUBNET:-172.30.0}.255`. Files it writes into the repository must belong to the host user, not root.
- Addresses .21, .22 and .30 are reserved for simulator containers that the lead adds later. Do not define them.

## 4. Channel Access proof (`emulation/tools/ca-proof.sh`, called by `make ca-proof`)
Known trap: two IOCs on ONE host do not both receive unicast Channel Access searches. Here each IOC has its own network namespace and address, which avoids it. Prove it, do not assume it. With both IOCs up, the script checks and prints PASS or FAIL per line, and exits non-zero on any FAIL:
- a) From a container on `mist2ctl`, with the subnet broadcast address in `EPICS_CA_ADDR_LIST` and `EPICS_CA_AUTO_ADDR_LIST=NO`: `IOC-RACK:heartbeat`, `IOC-RACK:mode`, `IOC-HV:heartbeat`, `IOC-HV:mode` are all read, and each heartbeat increases.
- b) Unicast to .11 only: the rack PV is found, the platform PV is not. Unicast to .12 only: the reverse. Both addresses in the list: both found.
- c) From the HOST network namespace of WSL (a container started with `--network host`, same broadcast address): all four PVs are read. This is how React Automation Studio's pvServer will connect, so it matters.
- d) `docker logs` of both IOCs contain no line that indicates a database, protocol, link or startup error. Decide which patterns to look for and list them in the script.

## 5. Device test harness (`emulation/devtest/`)
Other engineers will each write one device simulator plus database and test them in isolation, several of them AT THE SAME TIME on this Docker daemon. They call:

    emulation/devtest/run.sh <case-directory> [pytest arguments]

A case directory contains:
- `sim.yaml`: simulator configuration. The harness starts the simulator container (image `mist2-tools:dev`, repository mounted, `PYTHONPATH=/repo/emulation/sim`) with the command `python -m mist2sim --config /case/sim.yaml`. The command can be replaced by a one-line file `sim.cmd` in the case directory.
- `ioc.cmd`: iocsh lines for this case only, that is asyn port configuration and `dbLoadRecords`. It may use `$(SIM_HOST)` (host name of the simulator container) and `$(MIST2_DB)`. The harness wraps it between the standard prologue (as in `st.cmd`) and `iocInit`.
- `test_*.py`: pytest files, run in a third container (`mist2-tools:dev`) that reaches the IOC by Channel Access and the simulator by TCP. Environment for the tests: `SIM_HOST`, `IOC_HOST`, and Channel Access variables that point at this case's IOC only.
Requirements:
- `STREAM_PROTOCOL_PATH` is `$(MIST2_DB)` followed by the case directory, so a case can bring its own protocol file.
- Every run uses its own Compose project name and its own automatically assigned network (NO fixed subnet), so parallel runs from different worktrees cannot collide. It uses the worktree it is called from (mounts are derived from the script's location, not from a fixed path).
- It waits until the IOC answers, runs pytest, ALWAYS tears everything down, and exits with pytest's exit code.
- It saves the IOC log and the simulator log as `<case-directory>/build/ioc.log` and `build/sim.log`, readable by the tests while they run (a test may assert that the IOC log has no error lines) and by the engineer afterwards.
- Example case `emulation/devtest/example/`: a fake device of about 20 lines of Python (its own `sim.cmd`, answers a query with a number and acknowledges a set), a tiny protocol file and database inside the case directory, and tests that read a PV, write a set point, and check the IOC log. This example is your proof that the harness works without `mist2sim`.

## 6. `emulation/Makefile` and `emulation/README.md`
Targets: `build`, `up`, `down`, `restart`, `ps`, `logs`, `ca-proof`, `devtest CASE=<dir>`, `plan` (runs `python plan/build.py` in the tools container, writes `plan/out`), `plan-check` (runs it with `--out` pointing to a temporary directory, fails if the output contains `WARNING`, leaves `plan/out` untouched), and `test` (runs `pytest emulation/tests` in the tools container if that directory exists, otherwise says that the system tests are not there yet). All targets work when called as `make -C emulation <target>` from the repository root. The README lists the commands in one screen, plain and short.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    make -C emulation build
    make -C emulation up
    make -C emulation ca-proof
    make -C emulation devtest CASE=emulation/devtest/example
    make -C emulation plan-check
    make -C emulation down

All must exit 0, `ca-proof` must print PASS for a) to d), and after `down` no container or network of yours is left. Also run two `devtest` calls at the same time once, to show that they do not collide.

# Rules
- Do not invent facts. If something is unknown (a version, a flag, a behaviour), find it out by running it. What you cannot verify becomes a setting with a comment and a line in your report.
- Keep it small: no feature that is not asked for above.
- Leave no container running when you finish. Keep the images.
- Another engineer may be running Docker builds at the same time (React Automation Studio, its containers use the host network and names starting with `mist2ras`). Do not touch containers, images or networks that are not yours.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t1-ioc-image @ <commit>, worktree <absolute path>
    VERSIONS: EPICS base, asyn, StreamDevice tags, base image
    BUILT: what exists now, one line per deliverable
    VERIFIED: every acceptance command with its exit code and the key output lines, including the full PASS/FAIL list of ca-proof
    DECISIONS: choices you made that the brief left open, each with one reason
    ASSUMED: anything you could not verify
    NEEDS THE LEAD: changes outside your files, open questions, anything that did not work
