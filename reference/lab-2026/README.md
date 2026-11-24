# The lab's files of 2026-11-24

Copied by the owner from the rack computer (Windows, `C:\EPICS\IOCs\sampleIOC` and the checkout
of this repository there) on 2026-11-24, before that computer was wiped. Read-only, as found.
What they settle is in `docs/emulation/STATUS.md` (answer 39).

| File | What it is |
|---|---|
| `EPICS/st.cmd` | The start script of the lab's rack IOC, its last state: COM ports, line settings, which database with which macros |
| `EPICS/Db/IOC.faraday.db`, `IOC.flowmeters.db`, `matsusada_au20p15.db` | Databases that are not in the snapshot of 2023 |
| `EPICS/Db/IOC.mfc.db` | Changed since the snapshot of 2023 |
| `AVR/devices/FlowMeters/FlowMeters.ino` | The sketch of the flow meter Opta, an untracked file of the checkout on the rack computer |
| `some_notes.txt` | Notes of 2022: parity, COM ports, how to add a device |
| `start_epics.bat`, `open_valve.bat` | How the IOC was started |
| `rack-serial-devices.txt` | The serial ports and adapters Windows remembered, with COM number, USB ID and serial number: an extract of the device list |

Every other database and protocol file of the lab's IOC is identical to its copy in
`reference/lab-2023/EPICS/Db` (compared without line ends): `IOC.aim.db`, `IOC.interlockbox.db`,
`IOC.pressure.db`, `IOC.sensorbox.db`, `IOC.solenoidbox.db`, `IOC.thermocouples.db`, `aim.proto`,
`libcom1.db`, `libcom1.proto`, `matsusada_au20p7.db`, `matsusada_co_ctrl.proto`, `mfc.proto`,
`rek.db`, `rek.proto`, `tdk.db`, `tdk.proto`.

Not copied here: EPICS base 3.15.8 and the support modules, the built IOC, the previous control
system (`pycontrolsystem`), Dell's drivers, the full device list, and the log of the previous
control system (50 GB of exception messages from 2020-07 to 2022-02, no measured values).

The checkout on the rack computer was `master` at `3790bda` with local changes to three
sketches (`InterlockBox`, `SensorBox`, `Thermocouple`). The sketches of this branch hold those
changes (same pins) and differ only by the libcom1 protocol 2 work. The Arduino library folder
on the rack computer held libcom1 without protocol 2: the boards as last flashed answer the
query `A`, and neither identity nor acknowledged sets.
