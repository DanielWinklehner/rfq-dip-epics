# MIST-2 control system

Two EPICS IOCs (rack, HV platform) for the MIST-2 ion source, their simulators, a GUI (React
Automation Studio, `RAS/mist2`), loop service, logger, scan program and Arduino firmware.

Where the state of the work is written down. Read these before you act:

- `docs/emulation/STATUS.md`: done, open, the owner's answers (numbered), decisions with their
  reasons, assumptions (A..), open points (P..), questions to the owner.
- `docs/emulation/LAB-SETUP.md`: installation and first contact on the real computers.
- `docs/emulation/PLAN.md` and `docs/emulation/briefs/`: the tasks.
- `plan/controls.yaml`: the plan of the control system, every device and PV.

## The owner's rules, for every session

- Git: small commits with clear messages, never on `master`. The work branch is
  `emulated-iocs`. No pull request until the owner says so.
- Do not invent facts. If a protocol detail, a unit number, an address or a PV name is
  unknown, make it a configuration value, record the assumption in `STATUS.md`, and ask.
- Verify yourself: run a test or a check yourself before you accept a result. A report that
  says "done" is not evidence. Say plainly what was seen and what was not.
- Keep `docs/emulation/STATUS.md` current: done, open, decisions with reasons, every assumption.
- Do not rename existing PVs.
- Keep `plan/controls.yaml` current; `python plan/build.py` must run without warnings.
- No `sudo`: give the owner the command to run, in a fenced `bash` block, one command per block.
- The owner's name, e-mail address and the project's name go into no request to an outside
  service.

## Two sessions since 2026-11-25

- **The development session** runs on the owner's desktop PC, which is not on the lab's
  network. It has the emulation (Docker), leads the subagents, reviews and merges, and keeps
  the plan and the documents.
- **A lab session** runs on a computer of the lab's network (10.77.0.x; the lab computer is
  `mist-at-iba`, user `mist`, 10.77.0.1 on `eno1`, Ubuntu 26.04.1, with the site's network on a
  USB adapter by DHCP; the rack server and the platform computer hang on the same 10.77.0.x
  network, their addresses are not written down yet: ask, then write them here). It installs,
  reads the real devices, finds device names, edits `EPICS/ioc/iocBoot/*/ports.real.cmd` for
  them, and reports what the hardware answered.
- The two exchange through git only. A lab session pulls before each step
  (`git pull --rebase origin emulated-iocs`) and commits its results in small commits. The
  owner allowed pushes to `origin/emulated-iocs` in the development session (2026-11-24):
  a lab session asks him once before its first push.
- What the hardware showed goes into `STATUS.md` with the date and the words "seen on
  hardware", and closes or corrects the assumption or open point it belongs to.
- A lab session does not develop: a fault in a database, a protocol file or a sketch is
  described in `STATUS.md` (what was sent, what came back) for the development session.
  A change of one line that the hardware proves right (a device name, a baud rate) is fine.

## Real hardware: what a lab session may do

- **Reading is free:** `caget`, `camonitor`, device names (`ls -l /dev/mist2/
  /dev/serial/by-path/`, `udevadm info`), logs, and the read-only probes in `EPICS/ioc/host`.
- **Anything that switches something real needs the owner's word each time:** a `caput` to a
  valve, a pump, a supply or a relay; flashing a board; starting or restarting an IOC while
  something is pumping or under voltage (the first start after a boot restarts the valve
  box and releases its relays, see `LAB-SETUP.md`).
- The interlock box is a microcontroller with a program. It is not personnel protection.
