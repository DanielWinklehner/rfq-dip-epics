T16b: second part of the GUI round (T16): the data logger in the GUI, and three things the registry now gives. You are the engineer who built T16; your branch `emu/t16-loop-gui` is merged into `emulated-iocs` as it was.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Same worktree (`/home/daniel/code/rfq-dip-epics/.claude/worktrees/t16`) and branch. First discard the screenshots a check run of the lead left modified there (`git checkout -- RAS/mist2/tools/screenshots`), then `git merge --ff-only emulated-iocs`: you then have the data logger (T17: `logger/`, `docs/emulation/LOGGER.md`, a device `logger` of class `logger` with its state records `LOGGER:*` in the rack IOC), a fix of `loop.db` (the loop's reason, limit flag, output, error and terms are valid from the IOC's start on: processed once at the start), and plan revision 0.14 (below). Work only in your worktree, commit on your branch, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, never push.
- **Shared machine, now four users of one emulation**: the lead, the logger engineer, an engineer on the rack IOC's request records, and you. The rule is the same: the lock for the whole time the emulation is up (`flock /tmp/mist2emu.lock ...`), bring down what you started, never stop what you did not start, wait when the lock is taken. Expect to wait longer than before.
- You may change the one line of `plan/controls.yaml` that gives the logger's subsystem its page (G1), nothing else there. Do not raise the plan's revision. Commit regenerated files (`registry.json`, `plan/out/`) as a commit of their own at the end: the lead redoes it at the merge.

# What the lead verified of T16
The acceptance command (exit 0, 270 checks) and a session in a browser with the plant model at 20 A: set point 21 A typed into the loop's tag and PID from the tag (21 A after about 8 s, no window opened), a filament current typed into the supply's tag while in PID (hand-back "written by someone else"), the Plasma generator page out, PID from there, attached again, an entry given up by leaving the field, wheel and arrow keys. All as intended. Accepted and merged.

# Tasks
G1. **The data logger in the GUI.** Today its device has the page Diagnostics only because the GUI cannot show a device without a page: it stands as an empty tag in the list area of the Overview and of Diagnostics. Wanted:
   - A device whose subsystem has no page is infrastructure: it is on the Infrastructure page only, on no drawing and in no list area. Set the page of the subsystem `services` in the plan accordingly (the one line you may change) and make the GUI and `gui-check` accept it.
   - On the Infrastructure page the logger shows what its records say, from its roles (`docs/emulation/LOGGER.md` section 6, class `logger`: `alive`, `db`, `connected`, `disconnected`, `rows`, `buffer`, `dropped`, `count`): a widget for the class, role words in `roles.js`, a device window like every device.
   - The operator sees on every page that logging is dead: a chip for the logger in the status strip beside the IOCs' chips, from the role `alive`, in the shared alarm look. It is in the page windows too, because they have the strip.
   - Without the logger running (the emulation alone, `make -C emulation up`) `alive` is 0 with MAJOR alarm: that is the truth and the GUI shows it. `gui-check.sh` must pass in both states: the emulation alone, and with the logger up (`make -C logger up`, which needs no lock of its own but talks to the emulation). Decide how the check covers both without doubling its run time, and say so.
G2. **The loop's permits by their names.** The plan now has `labels` for `permit1` to `permit3` of the loop ("interlock closed", "REK on in remote control", "TDK output on") and `states` for `service` ("not alive", "alive"). Use them in the widget and the tag; remove the stand-in words from `registry.js` and their mirror in `gui-check.mjs`.
G3. **One list of trend roles.** The plan has `trends` (`roles`, and `beside`: a set point drawn in the graph of its read-back), written into the registry as `trends`. `roles.js` reads it from there instead of its own `trendRoles` and `trendBeside`. The logger's Grafana dashboards read the same key (the logger engineer does that side).
G4. **After an IOC start.** With the fix of `loop.db` the loop's records are no longer INVALID after a start of the platform IOC. Tighten what `gui-check` accepts after the IOC restart to the records that are still expected (the note names them); the request records of the rack IOC (`VALVE:s*:set`, `TURBO*:start:set`, `AIM:enable`) are another engineer's task (T18) and stay in the note until that is merged.

# Not in this round
- The owner's comments on the drawings (the lead applies them).
- Marking the filament heating supply's tag while the loop is in PID: a question to the owner, not answered yet.

# Acceptance (the lead runs it from your worktree)
    flock /tmp/mist2emu.lock bash -c 'make -C emulation up && make -C RAS/mist2 dev-up && RAS/mist2/tools/gui-check.sh; rc=$?; make -C RAS/mist2 dev-down; make -C emulation down; exit $rc'
Exit 0, and the same with the logger up as you describe it. The lead looks at the Infrastructure page, the strip and a page window with the logger running and stopped.

# Final report, with these headings
MODEL, BRANCH, BUILT, SHOWN (the logger: where, what, in which state which look), VERIFIED (commands, exit codes, numbers, how each new check was seen to fail), DECISIONS, NEEDS THE LEAD.
