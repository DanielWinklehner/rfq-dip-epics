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
| `test_01_startup.py` | Both IOC logs have no database, protocol, link or startup error; after the start only StreamDevice/asyn traffic messages; IOCs run with `sim` ports; simulator logs have no device error; every registry PV is connected and served by the IOC the registry names; each simulator's baud and bits per character equal the real port in `ports.real.cmd` |
| `test_02_read.py` | Every PV of every device answers and is not INVALID, except records never processed since the start (UDF) that are set or internal passive records, or belong to a `not_polled` device (asserted explicitly); libcom1 identity PVs name the simulator behind the device |
| `test_03_write.py` | Every written PV is written inside its test range, the set record ends without alarm and its read-back (processed after the write) follows; the device is restored |
| `test_04_ack.py` | An acknowledged set to a silent device ends INVALID and is not executed; an unanswered Matsusada set turns its echo INVALID and is not executed |
| `test_05_faults.py` | Per simulator, `silent`, `close`, `garbage`: every PV of the registry's fault list for that mode (`fails_with`, for `close` `fails_closed`) turns INVALID within its limit, no PV of the device outside the list does, no other PV of either IOC turns INVALID, the scanned ones keep updating, all recover after `clear`; one unit of a bus silent while its neighbours keep answering (rate reported); `trip` per type that has one; types without trip refuse it |
| `test_06_interlock.py` | An open door forces off the five AU supplies (rack IOC) and the REK (platform IOC); closing it brings the outputs whose request is set back ON by themselves (P16, asserted as it is); `AU:alloff:set` switches all five off and clears their requests |
| `test_07_update_rate.py` | Monitor update rate of the polled AU supplies of both chains and of the TDK, by Channel Access and by the simulator's counts, within 10 % of the bus arithmetic with even shares |
| `test_99_clean_end.py` | No fault and no held signal in any simulator, outputs off, valves closed, pumps stopped, set points as found, every PV back to its severity |

## Time limits and where they come from

| Limit | s | Source |
|---|---|---|
| IOC settled before the suite starts | 15 after the IOC start | GRACE 5 s (P20) and one NT 20 record period (8 s) |
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
| Door to output off / back | 3 / 5 | permit CP link, OutputIntlk scan 1 s, switching protocol PRIO HIGH |

Identity records are scanned every 10 s; the fault tests process them once after injecting and
after clearing a fault, so that the limits above apply to them and the suite stays under 10
minutes.

## Expected failures

None. The registry's two fault lists are checked in both directions: every PV of
`fails_with` turns INVALID under `silent` and `garbage` (except the NT 20 `raw` record, which takes
any line and must stay valid), every PV of `fails_closed` under `close`
(`test_05_faults.py::test_*`), and no PV of a faulted device turns INVALID without being in the
list of that fault (`test_05_faults.py::test_registry_fault_lists_name_every_pv_that_fails`).
