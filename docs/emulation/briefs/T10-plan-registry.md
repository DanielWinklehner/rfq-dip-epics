You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T10: bring the project plan in line with what was built, and generate the device registry that the GUI and the tests will use. A lead engineer wrote this brief, will run your acceptance test himself, and will merge your branch. Other engineers work in parallel on other files, so stay inside the files you own.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t10`, on branch `emu/t10-plan-registry`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never edit, stage or commit anything in `/home/daniel/code/rfq-dip-epics` outside your worktree. Check that `git -C /home/daniel/code/rfq-dip-epics/.claude/worktrees/t10 branch --show-current` prints `emu/t10-plan-registry`. If not, stop and report.
- Commit on that branch only. Small commits with clear messages. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04. `sudo` needs a password, so install nothing on the host. Host Python is 3.10 with PyYAML. Graphviz and python-docx are only in the container: `make -C emulation plan` and `make -C emulation plan-check` run `plan/build.py` there. Docker works without sudo.

# Read first
1. `plan/README.md`, `plan/controls.yaml` (the project owner's single source of truth: devices, connections, PVs, open questions) and `plan/build.py` (generates sketches and a Word document from it).
2. `docs/emulation/DESIGN.md` (approved design: section 1 says which PV names are the baseline, section 3 lists the devices, section 4 the turbopumps) and `docs/emulation/STATUS.md` (assumptions A1 to A22, open points P1 and following, findings).
3. What was built: every database in `EPICS/Db`, and how the two IOCs load them: `EPICS/ioc/iocBoot/iocRack/st.cmd` and `EPICS/ioc/iocBoot/iocHV/st.cmd`.
4. `docs/emulation/gui/LAYOUT.md` section 1.4 (widget classes and the PV roles each one asks for) and section 1.5 (pages and devices).
5. `reference/lab-2023/RAS/Devices.js`: the operators' labels (which valve is which, which temperature is which).

# Background
`plan/controls.yaml` was written before anything was built. It reads the PVs of each device from a SNAPSHOT of the databases (`plan/epics_db/`, taken at the start), knows one database per device, and still carries the PV prefixes of an older startup file. Since then the databases were reworked on the PV names of the lab's IOC, new devices got databases, and two emulated IOCs load them. The owner's rule: when a device gets a database, the YAML is updated so that its PVs show up as existing. And the new GUI must not have PV names scattered through its components: it gets ONE registry, generated from the YAML and the databases.

# Files you own
- `plan/controls.yaml`, `plan/build.py`, `plan/README.md`, `plan/registry.py` (new), `plan/epics_db/` (you may remove it), `plan/out/` (generated)
- `RAS/mist2/ReactApp/src/registry/registry.json` (new, generated) and a one-paragraph `README.md` next to it
- `emulation/Makefile`: only the targets `plan`, `plan-check` and a new `registry`
- `.gitignore`: only lines for `plan/out`
Nothing else. If you need a change elsewhere, describe it in your report.

# Deliverable 1: the plan matches what was built
- `plan/build.py` reads the live databases in `EPICS/Db` by default. The snapshot `plan/epics_db/` is no longer needed inside this repository: remove it, or keep it only if you can say what it is still good for.
- A device can be served by SEVERAL database loads (examples: the thermocouple board loads `thermocouples.db` and `libcom1_device.db`; a turbopump loads `turbo_pump.db` and `nt20_monitor.db`; the turbopump Opta loads `turbo.db` and `libcom1_device.db`). Extend the YAML and `build.py` for that in the simplest way that keeps existing entries readable.
- **Consistency check, the heart of this task**: `build.py` compares the database loads in the YAML (file and macros) with the `dbLoadRecords` lines of the two `st.cmd` files, and warns about every difference in either direction: a load in `st.cmd` that no device in the YAML claims, a load in the YAML that no `st.cmd` has, differing macros, a device on the wrong IOC. Records that belong to an IOC itself and not to a device (`ioc_info.db`) are assigned to the host entry. With this check, "the plan matches what was built" is something a command verifies.
- Update `plan/controls.yaml` to the state that was built. Keep the owner's wording, structure and open questions. Change only what the facts changed, and give a list of every change in your report, grouped by device, so that the lead can review it line by line. In particular:
  - the PV prefixes and database loads of every device as in the two `st.cmd` files;
  - PVs that were "proposed" and now exist come out of `proposed` (they then appear as existing, read from the database); proposed PVs that were NOT built stay proposed, and where DESIGN.md or STATUS.md says why something could not be built (for example `REK-1:mode:read`), add that as a note;
  - devices whose PVs were unknown and now have a database lose `pvs_unknown`;
  - notes and questions that the work has answered are updated or removed, with the answer kept as a note where it is worth knowing (for example the turbopump controller's relays, checked in its operating instructions). Questions that only the owner can answer stay. New open points from STATUS.md that concern a device go in as questions of that device;
  - what is still an ASSUMPTION (STATUS.md A1 to A22) must not read like a fact in the YAML: mark it as assumed in the note;
  - a new revision number and date in `meta`.
- Do not rename PVs, do not edit any database, and do not decide open questions yourself.
- `plan/out/`: by decision of the owner, the PDFs and the Word document stay under version control, PNG, SVG and other intermediate files do not. Arrange `.gitignore` and the index accordingly, and regenerate.

# Deliverable 2: the registry
`python plan/registry.py` writes `RAS/mist2/ReactApp/src/registry/registry.json` from `plan/controls.yaml`, the databases and the `st.cmd` files. It is generated, deterministic (same inputs give a byte-identical file), and the GUI and the test suite read nothing else to learn about devices and PVs. Design the format so that these users are served, and keep it as small as that allows:
- **The GUI** (LAYOUT.md 1.4 and 1.5): for each device its id, display name, model, widget class, subsystem and page, the IOC it lives on, the operators' labels for its channels where they exist, and its PVs BY ROLE (for a supply: voltage set point, voltage read-back, current set point, and so on; the roles per class are in LAYOUT.md 1.4, complete them from the databases where the table there is incomplete or out of date). Also every PV of the device with record type, unit and description for the expert page, the identity PVs of libcom1 devices, and per IOC its heartbeat and mode PVs.
- **The test suite**: every PV of every device with what a test needs to know about it: whether it is a value that is read or one that is written, for a written one its read-back and which value range is safe to write in a test, whether the set is acknowledged by the device, and which simulator (name in `emulation/sim/config/*.yaml`, host and control port) stands behind the device, so that a test can inject a fault into the right simulator and knows which PVs must go INVALID.
- Where this information belongs to the plan (class, labels, roles, test ranges), it is written ONCE in `plan/controls.yaml`, in a form the owner can read and edit, with rules per device class or per database rather than repeated per device. `registry.py` contains logic, not data about devices.
- `registry.py` runs the same consistency check as `build.py` (share the code) and fails with a clear message when YAML, databases and `st.cmd` disagree, or when a record in a loaded database has no role and is not marked as internal. That last check is what keeps the registry complete when someone adds a record later.
- A device that is installed but not polled (lens 3) and devices on assumptions (Faraday cup, the invented turbopump record format) carry a flag that the GUI can show.

# Acceptance test (the lead runs exactly this from the repository root of your worktree)

    make -C emulation plan-check
    make -C emulation registry
    git status --short
    make -C emulation plan

- `plan-check` exits 0 and prints no warning.
- `registry` exits 0, and `git status` afterwards shows no change: the committed registry is the generated one.
- `plan` regenerates `plan/out`, and afterwards only files that are meant to be tracked show as changed.
- Negative checks that the lead will make by hand, so try them yourself first: change a macro in one `st.cmd` line, remove one `dbLoadRecords` line, add a record to a database without giving it a role. Each must make `plan-check` and `registry` fail with a message that names the device and the file.

# Rules
- Do not invent facts about the machine. The YAML states what the owner wrote and what was built.
- Keep it small. `registry.py` and the additions to `build.py` should be readable in one sitting.
- Leave no container running when you finish.

# Final report (plain text, this format)
    MODEL: ...
    BRANCH: emu/t10-plan-registry @ <commit>
    BUILT: one line per deliverable
    YAML CHANGES: every change to plan/controls.yaml, grouped by device: what it said, what it says now, why
    YAML SCHEMA: the new keys, with one example each
    REGISTRY FORMAT: the structure of registry.json with a shortened example of one device of each class
    VERIFIED: the acceptance commands with exit code and key output, and the three negative checks with their messages
    COUNTS: devices, existing PVs and proposed PVs before and after
    DECISIONS: choices the brief left open, each with one reason
    NEEDS THE LEAD: changes outside your files, open questions, anything in the YAML you were not sure you may change
