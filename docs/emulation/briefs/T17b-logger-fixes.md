T17b: fix round of the data logger (T17), from the lead's review and hands-on session of 2026-11-22. You are the engineer who built it; your branch `emu/t17-logger` is merged into `emulated-iocs` as it was.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Same worktree (`/home/daniel/code/rfq-dip-epics/.claude/worktrees/t17`) and branch. First `git merge --ff-only emulated-iocs`: you then have the GUI round (T16: values set in place, tabs as windows, the loop's widget), a fix of `loop.db`, and a plan with `trends` (below). Work only in your worktree, commit on your branch, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, never push.
- **Shared machine, now four users of one emulation**: the lead, the GUI engineer, an engineer on the rack IOC's request records, and you. The rule is the same: the lock for the whole time the emulation is up (`flock /tmp/mist2emu.lock ...`), bring down what you started, never stop what you did not start, wait when the lock is taken. Expect to wait longer than before.
- Do not raise the plan's revision. Commit regenerated files (`registry.json`, `plan/out/`) as a commit of their own at the end: the lead redoes it at the merge.

# What the lead verified (so you know what holds)
The three acceptance commands exit 0 in his run (271 passed in 697 s; 28 passed in 332 s). With the plant model in PID at 22 A he captured `REK-1:current:read` with his own monitor for 90 s, stopped the database for 32 s and opened the door: 533 updates, 533 raw rows, none missing, none extra, none different; the seconds tier equal to his own time-weighted means in 87 of 87 seconds. That part is accepted.

# Findings to fix
F1. **The loop's writes fill the tables that are kept for ever.** While the loop is in PID the service writes `TDK:current:setpoint` up to five times a second. It is a written PV, so every write became a `set` event and a row in `changes`: 63 set events in 78 s of PID in the lead's session, 66 of the 135 events of those four minutes. A day of PID is about 70 000 rows in each of the two tables, for ever, and the event log of a day cannot be read any more. Wanted: while a loop is in PID, what it writes to its actuator is a signal, kept like a measured value (raw, seconds, minutes) and not as set commands. Outside PID a write to the same PV is a set command like any other and is in the event log. The loop's own mode events mark the border. Which PV a loop writes is in the plan (macro `ACT` of `loop.db`, `mode` role of the loop): derive it from there, name no PV in the logger, and a second loop added to the plan must behave the same without a change in the logger. Say in LOGGER.md what a reader finds where, and correct the sizing for a day in PID.
F2. **The reason in a mode event is the one before the hand-back.** In the session the event `LOOP-DIS:mode:get PID -> MANUAL` carried the detail `LOOP-DIS:reason:get: none (0)`, and the reason "interlock open" came 0.06 ms later as an event of its own. The loop's records are written in this order (request, mode, reason), a refusal the same. The detail must be the reason that belongs to this change of mode. A test with the real order of the records.
F3. **Grafana never shows finer than one minute.** A dashboard over the last 5 minutes drew one value per minute (screenshot of the lead: steps at the full minutes, nothing after the last full minute), although raw data of the same time exists. `$__interval_ms` has a lower limit in Grafana that the provisioning does not set. Wanted: a window of minutes shows raw data, the tier follows the window as LOGGER.md says, and the newest data is visible up to the few seconds the logger needs. A test that asks Grafana (its query API, as a viewer) for a short window of a 10 Hz PV and counts the points.
F4. **The dashboards do not have the loop.** The GUI draws the loop's measured value with its set point in one graph and its output in a second one (T16); the dashboards have neither, because `dashboards.py` has its own copy of the GUI's trend roles. The plan now has them once: `trends` in `plan/controls.yaml` (`roles`, and `beside`: a set point drawn in the graph of its read-back), written into the registry as `trends`. Read them from the registry. Add a check to `plan/build.py` that warns about a role in `trends` that no database has. (The GUI engineer switches `roles.js` to the same key; do not touch `RAS/` except the generated registry.)
F5. **A batch the database rejects blocks the writer for ever.** `Store._run` treats every `psycopg.Error` as a lost database and tries the same batch again. For a lost connection that is right. For a batch the database refuses (a data or integrity error) it means: the buffer fills, then everything is lost until somebody notices. Wanted: the batch that cannot be written is given up after the database has answered with such an error, its rows counted as lost, an event with the database's message, and the writer goes on. A test that puts a bad row into a batch.
F6. Small: `env.template` says 124 rows per second, LOGGER.md 139.6. One number, with its source.

# Not yours in this round
- The logger's device in the GUI (a widget, the Infrastructure page only): the GUI engineer does it and moves the device's page in the plan.
- `old` of the first set event after an IOC start, for a record that was never processed: leave it, another task changes those records.

# Acceptance (the lead runs these from your worktree)
    flock /tmp/mist2emu.lock make -C emulation plan-check
    flock /tmp/mist2emu.lock make -C emulation test
    flock /tmp/mist2emu.lock make -C logger test
All exit 0, saved settings unchanged, the suite under 13 minutes. The lead repeats his session: PID for some minutes, then the events of that time, the mode event's detail, and a dashboard over 5 minutes.

# Final report, with these headings
MODEL, BRANCH, FIXED (one paragraph per finding: what was wrong in the code, what it does now, the test and how it was seen to fail), VERIFIED (commands, exit codes, numbers), DECISIONS, NEEDS THE LEAD.
