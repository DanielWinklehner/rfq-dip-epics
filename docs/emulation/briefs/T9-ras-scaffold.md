You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T9. A lead engineer wrote this brief, will run your acceptance test himself, and will merge your branch. Other engineers work in parallel on other files, so stay inside the files you own.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t9`, on branch `emu/t9-ras-scaffold`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. `/home/daniel/code/rfq-dip-epics` itself is the lead's worktree: never edit, stage or commit anything there. Check that `git -C /home/daniel/code/rfq-dip-epics/.claude/worktrees/t9 branch --show-current` prints `emu/t9-ras-scaffold` and that `docs/emulation/DESIGN.md` exists in your worktree. If not, stop and report.
- Commit on that branch only. Small commits with clear messages. Never commit on `master` or `emulated-iocs`. Never push, never open a pull request.
- Read first: `docs/emulation/DESIGN.md` (sections 2 and 5), `docs/emulation/PLAN.md`, `RAS/README.md` and `RAS/IsoDAR/` (the old GUI from 2021, for orientation only).
- Host: WSL2 Ubuntu 22.04, 28 cores, 94 GB RAM. `sudo` needs a password, so install nothing on the host (there is no Node on the host, use containers). Docker 29.9 (a native engine inside WSL, not Docker Desktop) and Docker Compose 5.6 work without sudo. The user opens the GUI from a browser on Windows.

# Background
The GUI of this control system is built with React Automation Studio (RAS), release V8.1.0 (May 2026). Custom applications start from the boilerplate repository `https://github.com/React-Automation-Studio/React-Automation-Studio-Example-Project-1`, which pulls RAS in as a git submodule (`submodules/React-Automation-Studio`). RAS's Docker setup uses host networking and its README advises against platforms other than Linux, so it runs inside WSL2.

The EPICS IOCs that the GUI will talk to are emulated: two containers on a Docker bridge network `172.30.0.0/24` (rack IOC at `.11`, platform IOC at `.12`), built by another engineer right now. They are not available to you yet. Each serves a test PV: `IOC-RACK:heartbeat` and `IOC-HV:heartbeat` (a counter that goes up once per second) and `IOC-RACK:mode`, `IOC-HV:mode` (a string, `sim` or `real`). RAS's pvServer runs with host networking and must find PVs on that bridge network through the subnet broadcast address (`EPICS_CA_AUTO_ADDR_LIST=NO`, `EPICS_CA_ADDR_LIST=172.30.0.255`).

# Goal
The new GUI application exists in this repository as an empty but running shell, and it is proven that its pvServer reads a PV from each of two IOCs that live on a Docker bridge network. No pages yet: the page layout is decided separately.

# Files you own
- `RAS/mist2/` (new, everything below it)
- `.gitmodules` (new, for the RAS submodule)
Do NOT touch `RAS/IsoDAR/`, `RAS/README.md`, `EPICS/`, `emulation/`, `plan/`, `docs/`. If you need a change elsewhere, describe it in your report.

# Deliverables

## 1. `RAS/mist2/` from the boilerplate
- Take the boilerplate at its current head (it is on RAS V8.1.0; record the exact commit you copied from in `RAS/mist2/UPSTREAM.md`, together with how to update to a later RAS release). Copy its files, not its git history. Keep its license file.
- Add React Automation Studio as a git submodule at `RAS/mist2/submodules/React-Automation-Studio`, pinned to the tag `V8.1.0`. Check that `git submodule status` shows that tag.
- Reduce the application to what this project needs. Our rule for the new GUI is: no placeholder PVs, no dead code. So the demo pages, demo IOCs, staging examples and example components of the boilerplate do not stay in OUR application code (`RAS/mist2/ReactApp/src`) and are not started by OUR compose files. Do not modify files inside the submodule. Where the boilerplate needs a service only for features we do not use yet (alarm handler, load/save, Signal notifications, style guide, three-node database), find out by experiment what the minimum is that still gives a working pvServer and frontend, keep that, and list what you removed and what it would take to bring each back. Do not guess: start it and see.
- Login stays disabled for now (development on a private machine). Say in your report what enabling it later involves.

## 2. One page that proves the data path
- The application has exactly one route for now: a page titled "MIST-2" that shows, with standard RAS components, the four test PVs above: heartbeat and mode of both IOCs. Use the RAS component that colors by EPICS alarm severity where one exists. If a PV is disconnected the page must show that, not a stale or empty value.
- No other PV names anywhere in our application code.

## 3. Start and stop
- `RAS/mist2/Makefile` (or scripts) with `dev-up`, `dev-down`, `dev-logs`, and `build` if it is a separate step. Compose project name `mist2ras`, so that its containers are recognisable. All Channel Access settings in ONE place (`RAS/mist2/.env` created from a committed template; do not commit secrets).
- Ports: RAS uses the host network. List every port it listens on and check before starting that none is taken.
- Say which URL the user opens from the Windows browser, and verify from inside WSL with `curl` that the page and its JavaScript are served.

## 4. Proof script `RAS/mist2/tools/pv-proof.sh`
Until the real emulated IOCs exist, build a stand-in that has the SAME network situation, on a DIFFERENT subnet so that you do not collide with the other engineer: a Docker bridge network `172.31.0.0/24` with two containers, each running a soft IOC (the `softIoc` of an EPICS base image, for example the one the RAS compose files build) that serves `IOC-RACK:heartbeat` + `IOC-RACK:mode` at `.11` and `IOC-HV:heartbeat` + `IOC-HV:mode` at `.12`. The script:
- takes the subnet prefix as an argument (default `172.30.0`, the real emulation; you test with `172.31.0`) and an option that starts and stops the stand-in IOCs,
- checks that the running pvServer, configured for that subnet, delivers a CHANGING value of both heartbeat PVs and the value of both mode PVs. "Delivers" means through the pvServer's own client interface (the Socket.IO connection that the browser uses, from a small script in a container), or through a headless browser that loads our page and reads the four values from the rendered DOM. A line in the pvServer log is not enough.
- prints PASS or FAIL per PV and exits non-zero on any FAIL.
If you find that host-network pvServer plus bridge-network IOCs does NOT work with a broadcast address, find out why and what does work (unicast list, name server, attaching pvServer to the bridge network as well), and report it clearly: the emulation design depends on this.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    git submodule status                       # shows V8.1.0
    make -C RAS/mist2 dev-up
    RAS/mist2/tools/pv-proof.sh 172.31.0 --with-standin-iocs
    curl -sf <the URL you documented> >/dev/null
    make -C RAS/mist2 dev-down

All must exit 0, and after `dev-down` no container or network of yours is left. The first build may take 20 to 30 minutes, that is expected.

# Rules
- Do not invent facts about RAS: its source is in the submodule, read it. What you cannot verify becomes a setting with a comment and a line in your report.
- Another engineer is building EPICS images and containers at the same time (names `mist2emu`, `mist2-ioc`, `mist2-tools`, network `172.30.0.0/24`). Do not touch containers, images or networks that are not yours.
- Never commit `node_modules`, build output or a real `.env`.
- Leave no container running when you finish. Keep the images.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t9-ras-scaffold @ <commit>, worktree <absolute path>
    UPSTREAM: boilerplate commit, RAS submodule commit and tag
    BUILT: what exists now, one line per deliverable
    SERVICES: which containers run in development, what each is for, which ports, and what you removed from the boilerplate
    VERIFIED: every acceptance command with exit code and key output, including the PASS/FAIL list of pv-proof
    HOW RAS WORKS (for the engineers who build the pages next, half a page): how a PV name is written in a component in V8.1.0 (prefixes, macros), how alarm severity reaches a component and which components use it, how routes and the layout with tabs are defined, where custom components go, how the development server picks up changes
    DECISIONS: choices you made that the brief left open, each with one reason
    ASSUMED: anything you could not verify
    NEEDS THE LEAD: changes outside your files, open questions, anything that did not work
