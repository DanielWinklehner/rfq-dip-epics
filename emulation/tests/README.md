# System tests of the emulation

`make -C emulation test` (from the repository root) starts the emulation if it is not running,
waits for both IOCs, runs this suite in the `tools` container, prints the update-rate table and
exits with pytest's exit code. An emulation that was running stays running; one it started, it
stops. Arguments go to pytest: `make -C emulation test ARGS="-k valve"`,
`ARGS="emulation/tests/test_05_faults.py"`. The IOC and simulator output of the run is saved in
`emulation/build/<service>.log` (the tests read the IOC logs there), the rate table in
`emulation/build/update-rate.md`. `ARGS="-m slow"` runs only tests marked slow (there are none
at present), `ARGS='-m ""'` everything.

Device and PV names come from the registry (`RAS/mist2/ReactApp/src/registry/registry.json`):
the tests are parametrised over its devices, PVs, written PVs, simulators and units, so a device
added to the registry is tested without a new line here. Shared code: `system.py` (registry,
Channel Access, simulator control, waits), `conftest.py` (wait for both IOCs, snapshot of the
state found, restore at the end, also after a failure).

## What each module proves

| Module | Proves |
|---|---|
| `test_01_startup.py` | Both IOC logs have no database, protocol, link or startup error; until the first fault a test injects not a single traffic or connection message ("autoConnect could not connect", "port ... not connected": a device unreachable at the start); afterwards only StreamDevice/asyn traffic messages; IOCs run with `sim` ports; simulator logs have no device error; every registry PV is connected and served by the IOC the registry names; each simulator's baud and bits per character equal the real port in `ports.real.cmd` |
| `test_02_read.py` | Every PV of every device answers and is not INVALID, except records never processed since the start (UDF) that are set or internal passive records (asserted explicitly); every alias answers with its record's value and severity; spare channels are read and valid; libcom1 identity PVs name the simulator behind the device |
| `test_03_write.py` | Every written PV (also the AU and REK current limits) is written inside its test range, the set record ends without alarm and its read-back (processed after the write) follows; the device is restored, a limit to exactly the value it had (it is saved by autosave); switching on sends the saved limit, also to a supply that forgot it |
| `test_04_ack.py` | An acknowledged set to a silent device ends INVALID and is not executed; an unanswered Matsusada set turns its echo INVALID and is not executed, except the current limit, which is sent again until applied and arrives after the fault |
| `test_05_faults.py` | Per simulator, `silent`, `close`, `garbage`: every PV of the registry's fault list for that mode (`fails_with`, for `close` `fails_closed`) turns INVALID within its limit, no PV of the device outside the list does, no other PV of either IOC turns INVALID, the scanned ones keep updating, all recover after `clear`; one unit of a bus silent while its neighbours keep answering (rate reported); `trip` per type that has one; types without trip refuse it |
| `test_06_interlock.py` | An open door forces off the four AU supplies (rack IOC) and the REK (platform IOC) and clears their requests; a request while it is open is cleared at once; closing it switches nothing on (latch, owner's decision); switching on again works; `AU:alloff:set` switches all four off and clears their requests |
| `test_08_local.py` | One AU supply and the REK: the front panel takes local control, status:read shows it (MINOR) through status polls, a voltage set ends INVALID and is not executed, switching from the control system takes control back |
| `test_07_update_rate.py` | Monitor update rate of the polled AU supplies of both chains and of the TDK, by Channel Access and by the simulator's counts, within 10 % of the bus arithmetic with even shares |
| `test_09_loop.py` | The control loops (`docs/emulation/LOOP.md`), without the plant: every setting written and read back, the set point limits (records `spmin`, `spmax`) clamp the set point and bring it along when moved inside it; each permit record reads as words, not fulfilled without alarm; an output limit moved past the actuator in PID brings it to the new limit at the slew rate, with output:get telling the truth; PID refused while a permit fails, with stale data, outside the output limits, with the service stopped (R5); each hand-back from PID with its reason and time limit, request back at MANUAL, actuator left where it was (permits, measurement INVALID, permit without data, stale heartbeat, someone else writes the actuator, the actuator does not accept a set, the service killed); a restart of the service and of the IOC end in MANUAL; the backstop with a test client in the service's place: no value outside the output limits, no step above slew x DT, no write in MANUAL, from outside the limits only towards them, a lowered maximum followed at the slew rate, none after someone else wrote, MANUAL when the client stops counting |
| `test_10_lost_permit.py` | A lost permit (the rack IOC stopped: its connection closes; paused: it goes silent): the REK, which takes its permit from the rack IOC, switches off, its request is cleared, a request while lost is cleared at once, nothing comes back when the permit returns; the discharge loop in PID hands back with "permit 1 no data"; a platform IOC started while the rack IOC is down cannot switch the REK on, and the loop refuses PID. The AU supplies have the same records but their permit is in their own IOC |
| `test_99_clean_end.py` | No fault and no held signal in any simulator, outputs off, valves closed, pumps stopped, set points as found, every PV back to its severity, every loop in MANUAL |

## Time limits and where they come from

| Limit | s | Source |
|---|---|---|
| IOC settled before the suite starts | 15 after the IOC start | GRACE 5 s and one NT 20 record period (8 s) |
| Permit gates enabled (first contact) | 30 | probe every 1 s, then GRACE 5 s after the supply's first answer |
| Limit applied by the retry after a fault | 8 | sent again every SCAN_GET (5 s) while not applied |
| Local control kept / shown | 2 polls / 3 | status:read every 1 s |
| Outputs stay off after the door closed | 2 gate scans | OutputIntlk scans every 1 s |
| First value of every PV | 10 | NT 20 data output every 8 s |
| Echo or state read-back after a write | 5 | Matsusada `:get` read by forward link behind the chain's polls (device test 3 s), MFC read-backs every 2 s |
| Measured output follows a set point | 10 | TDK time constant 0.1 s, polled at 10 Hz (TDK device test) |
| Device back to its severity after a test | 15 | nAIM strikes for some seconds after switching on |
| Fault to INVALID, default | 5 | slowest poll 2 s (MFC) plus a reply timeout of at most 1 s |
| Fault to INVALID, Matsusada | 8 | echoes and SW setting every 5 s, each poll of a silent unit waits 200 ms |
| Fault to INVALID, NT 20 monitor | 25 | one record every 8 s, AGE_LIMIT 20 s, age scanned every 1 s |
| NT 20 garbage seen | 13 | one record period (8 s), then two 1 s scans with a record that does not parse |
| Recovery after clear | 20 | asyn reconnect plus next poll |
| Other devices keep updating | 5 | every PV processed at least every 2 s (found by observation) |
| Listed PVs stay INVALID | 1; 8 for Matsusada `close` | two watchdog restarts of the monitor cycle (POLL_LIMIT 30 x 0.1 s) |
| No INVALID before a fault | 1 | the previous test's device has settled |
| Door to output off / back | 3 / 5 | permit CP link, OutputIntlk scan 1 s, switching protocol PRIO HIGH |
| Permit lost: connection closed / peer silent | 2 / 13 | the mirror `_permit:read` scans every 0.1 s / `EPICS_CA_CONN_TMO` 5 s of the platform IOC, then an echo unanswered for another 5 s (measured 0.4 to 0.6 s and 9.8 to 10.0 s) |
| Loop: refusal | 1 | the service reads the request by monitor, decides in its next cycle (0.2 s) |
| Loop: hand-back, interlock / supply off | 1 / 2.5 | interlock box polled every 0.1 s / output state polled every 1 s, then one cycle |
| Loop: hand-back, measurement INVALID / permit without data | 2 / 3 | REK monitors at 10 Hz, reply timeout 150 ms / interlock box reply timeout 1 s |
| Loop: permit link lost, connection closed / peer silent | 2 / 13 | as the supply's gate: `_c1` scanned every 0.2 s / `EPICS_CA_CONN_TMO` 5 s and an echo |
| Loop: output limit moved past the actuator | distance / slew + 2 | the writer moves at slew x DT per period |
| Loop: hand-back, actuator written by someone else / set not accepted | 1 / 1 | the monitor reaches the service at once / a garbled answer fails at once; one cycle |
| Loop: hand-back, stale | stale time + 1.5 (and not before stale time - 1.2) | heartbeat counts once per second, plus one cycle |
| Loop: service stopped or killed | watchdog time + 0.5 | `service:get` scans every 0.1 s, then CP links |
| Loop: service or IOC back | 30 | the container's start, GRACE of the supplies |

Identity records are scanned every 10 s; the fault tests process them once after injecting and
after clearing a fault, so that the limits above apply to them and the suite stays under 12
minutes (about 12 with the loop tests and the lost permits).

## Saved settings

At its start the suite prints every saved setting (the PVs of the IOCs' `limits.defaults`) that
differs from its default, and restores what it found at the end. `run.sh` reads `limits.sav` of
every IOC before and after the run (after the emulation stopped, or 6 s after the tests when it
stays running) and fails when the run changed it.

## Containers stopped by the tests

The tools container has no Docker. `test_09_loop.py` stops, starts, restarts and kills the loop
service and restarts the platform IOC through `run.sh`: a test writes a request file into
`emulation/build/docker-requests/`, `run.sh` runs `docker compose <action> <service>` for the
services `ioc-rack`, `ioc-hv` and `loop` only, and follows the new log of a started container
(`system.container()`).

## Test C: the loop on the plant

`make -C emulation test-loop` runs `loop_plant.py` with the plant model (`MIST2_PLANT=1` for
`run.sh`; a plant it started is stopped again). It brings the source to about 20 A of discharge
current in MANUAL, switches to PID, steps the set point to 22 A, drifts the emission, lowers the
REK's current limit under the set point and restores it, and hands back in closed loop. The
table with its pass limits (each with its source in `loop_plant.py`) is printed and saved in
`emulation/build/loop-plant.md`. About 3 minutes.

## Expected failures

None. A test that shows something wrong in a database, a simulator, the registry or a startup
file is marked as a strict expected failure with its reason, and listed here.

The registry's two fault lists are checked in both directions. Every PV of `fails_with`
must turn INVALID under `silent` and `garbage` and stay INVALID while the fault lasts. The
exception is the NT 20 `raw` record, which takes any line and must stay valid under `garbage`.
The same holds for every PV of `fails_closed` under `close` (`test_05_faults.py::test_*`). No PV
of a faulted device may stay INVALID without being in the list of that fault
(`test_05_faults.py::test_registry_fault_lists_name_every_pv_that_fails`).

## Registry keys

Used: `roles`, `channels` (labels, `spare`), `states` of a PV (status words of the Matsusada
supplies), `aliases`, `test`, `ack`, `readback`, `note` (read by a person, not by the code),
`sim`, `fails_with`, `fails_closed`, `simulators`, `iocs`. Not used, GUI only: `confirm` (a
question to the operator before a write), `labels`, `page`, `subsystem`, the `not_installed` flag
(turbopump 2 is simulated and tested like any other device), device-level `states`.
