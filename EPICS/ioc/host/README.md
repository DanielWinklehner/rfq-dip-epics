# Rack computer on Linux: the Matsusada USB adapters and the serial device names

**Not tested on hardware.** Everything here was written without the adapters and devices. Both
rule files pass `udevadm verify` (Ubuntu 24.04, systemd 255), and the probe was run against the
Matsusada simulator through a pseudo serial port.

## What is known

| Fact | Source |
|---|---|
| The CO-U32 holds an FTDI USB-serial chip. Matsusada's Windows driver is FTDI's driver 2.08.28 with two INF files that name Matsusada's USB ID | Matsusada driver CD rev. 1.7.0: `Drivers/MTPBUS.inf`, `Drivers/MTPPORT.inf`, installation guide section 1-2 |
| USB ID: vendor `1192`, product `1000` | The same INF files, and the owner's notes of about 2016 (`setVIDPID(0x1192, 0x1000)` on a Raspberry Pi) |
| Matsusada's current driver package is still FTDI's driver (2.12.36.20 of 2024) and still names this one ID only | `mp_-lus1_usb-driver_for_win10-11_rev.2.12.36.20.zip` from Matsusada's web page, downloaded by the owner on 2026-11-22: `mtpbus.inf`, `mtpport.inf` |
| Serial number of the CO-U32: `CO001144` | The owner's notes |
| Line: 9600 baud, 8 data bits, no parity, 1 stop bit, no flow control. A command ends with CR | Matsusada's sample programs, the owner's notes, `EPICS/Db/matsusada_co_ctrl.proto` |
| Every entry of the INF's baud rate table is the plain FTDI divisor (9600 baud is 3 MHz / 312.5), so 9600 baud means the same on Linux | `MTPPORT.inf`, `ConfigData` |
| Linux does not list the ID: `ftdi_sio` has no entry for `1192:1000` | `drivers/usb/serial/ftdi_sio_ids.h`, kernel mainline of 2026-11-22 |

So the adapter needs no new driver. Without a driver that knows the ID it is on the USB bus but
gets no serial port, on Windows and on Linux alike. Windows learns the ID from Matsusada's INF
files. On Linux the kernel's own FTDI driver takes the chip once one line names the ID to it,
and the adapter is then an ordinary serial device, which asyn opens with
`drvAsynSerialPortConfigure` as it does on Windows. The route of 2016 (FTDI's D2XX library, a
Python wrapper, root rights for every run) is not needed.

## Files

| File | Purpose |
|---|---|
| `99-mist2-matsusada.rules` | udev rules: name the ID to `ftdi_sio`, keep ModemManager off the line, and create `/dev/mist2/co-u32` for the adapter with the serial number `CO001144`. That name works only if the adapter reports the serial number under Linux; Windows saw none (below) |
| `99-mist2-serial.rules` | udev rules: `/dev/mist2/gauges`, `interlock`, `valves` and `mfc` by USB ID and serial number, each line with its source (the Windows device list of 2026-11-24 and the lab's `st.cmd`) |
| `matsusada_probe.py` | First contact without an IOC: asks each unit for status, settings and monitors, prints the replies and the reply times. Read-only by default (no set command, no `REN`). With `--remote` it sends `REN` before a unit's queries and `GTL` after them, because the supplies answer the settings only under remote control (seen on 2026-11-24) |
| `build-epics.sh` | Builds EPICS base, asyn, StreamDevice, autosave (the release tags of the `mist2-ioc` image) and the IOC application on the computer, into `/opt/epics` or a directory given as argument. Run in fresh containers of Ubuntu 20.04, 22.04 and 24.04, where both IOCs then started in `real` mode with no device; not on the lab's computers |

The steps of a first installation, in order: `docs/emulation/LAB-SETUP.md`.

**INFICON VGC401 (foreline gauge controller, task T30).** `inficon_vgc401_probe.py <device>
[baud]` is the read-only first contact: it listens 3 s without sending (after power-on the
controller sends a value every second by itself), then asks once each for the pressure (`PR1`),
the unit (`UNI`), the gauge (`TID`), the error word (`ERR`) and the firmware number (`PNR`),
and prints the raw replies with their times and a last line with how many answered (exit code
0: all five). It sends no mnemonic with a parameter; its first character ends the automatic
transmission and reading `ERR` clears the error word, both as the manual (tinb01e1-f, p. 55, 63)
describes. Python 3 standard library only, 9600 baud unless given. `inficon_vgc401_fake.py`
runs it against a fake controller on a pseudo-terminal (exit 0; with `--silent` a controller
that never answers, exit 1). Cable, line settings and what the output means:
`docs/emulation/VGC401.md`.

## Install (once, with root rights)

```bash
sudo cp EPICS/ioc/host/99-mist2-matsusada.rules EPICS/ioc/host/99-mist2-serial.rules /etc/udev/rules.d/
```

```bash
sudo udevadm control --reload
```

The user that runs the IOC must be in the group `dialout` (`sudo usermod -aG dialout <user>`,
then log in again). Then plug the adapter in, or pull it and plug it in again.

## Check with the adapter

Use a second PC or a Linux live system, not the Windows installation of the production IOC.
These are 20 kV supplies: keep the outputs off.

| Step | Command | Expected |
|---|---|---|
| 1. The adapter is on the bus | `lsusb -d 1192:` | One line with `1192:1000` |
| 2. The driver took it | `sudo dmesg \| grep -i -E "ftdi\|ttyUSB" \| tail` | `FTDI USB Serial Device converter now attached to ttyUSB0` |
| 3. The name exists | `ls -l /dev/mist2/ /dev/serial/by-id/` | `co-u32 -> ../ttyUSB0`, and a name in `by-id` that holds the serial number |
| 4. The supplies answer | `EPICS/ioc/host/matsusada_probe.py /dev/mist2/co-u32 3 4` | Six replies per unit in the form the protocol file expects. Compare them with the front panels |
| 5. Reply times | The same with `--repeat 100` | The median, for the update rate arithmetic in `plan/controls.yaml` |

If step 1 shows another ID or step 3 another serial number, correct the rule file, copy it
again and reload. After step 4 the IOC can use the adapter. The acceptance test of
`plan/CO-U32_driver_brief.md` (one hour of polling at 10 Hz without a timeout; pull and plug
the adapter without an IOC restart) is done with the IOC.

The check may also work in WSL2: the WSL kernel 6.18 has `ftdi_sio` as a module and runs udev.
Windows must hand the adapter to WSL with `usbipd-win`, which is not installed on the
development PC. Not tried.

## Read the IDs and serial numbers on the Windows IOC

Both open questions (A29, P34) can be answered on the rack PC as it is, in PowerShell:

```powershell
Get-PnpDevice | Where-Object InstanceId -match 'VID_1192' | Format-Table Status, FriendlyName, InstanceId -AutoSize
```

It reads the device list and changes nothing. An instance ID has the form
`USB\VID_1192&PID_1000\<serial number>`. Adapters that were installed once and are not
plugged in are listed too. The command was run on the development PC, which has no such
device: it lists nothing there.

## The names of the other serial devices

From the list of serial devices Windows on the rack computer remembered on 2026-11-24
(`reference/lab-2026/rack-serial-devices.txt`), joined by COM number with the lab's `st.cmd`
of 2026 and its notes (`reference/lab-2026`):

| Device | COM | USB ID | Serial number | Name |
|---|---|---|---|---|
| Gauge controller (Teensy) | 6 | `16c0:0483` | `3596460` | `/dev/mist2/gauges`, `99-mist2-serial.rules` |
| Interlock box (Mega) | 11 | `2341:0042` | `954323138373519002A2` | `/dev/mist2/interlock`, `99-mist2-serial.rules` |
| Valve box (Mega) | 12 | `2341:0042` | `95433343733351502071` | `/dev/mist2/valves`, `99-mist2-serial.rules` |
| MFC (FTDI to RS-485) | 13 | `0403:6001` | `FTJRNRWQ` | `/dev/mist2/mfc`, `99-mist2-serial.rules` |
| TDK (FTDI), platform computer, notes of 2022 | 8 | `0403:6001` | `A5051Z0G` | not in these files (platform IOC) |
| Matsusada adapters (three entries) | 7, 9, 15 | `1192:1000` | none: named after the USB socket | `by-path` |
| nAIM (Prolific) | 3 | `067b:2303` | none: named after the USB socket | `by-path` |
| REK (Prolific), platform | 19 | `067b:2303` | none | `by-path` (platform computer) |
| Thermocouples (Arduino Micro), platform | 22 | `2341:8037` | none | `by-path` (platform computer) |
| Faraday cup Opta | 16 | `2341:0164` | listed with an interface's instance ID, no serial number per COM number | `by-path` |
| Flow meter Opta | 23 | `2341:0164` | as above | `by-path` |

A device without a serial number gets the name of its USB socket: plug in one device at a
time, `ls -l /dev/serial/by-path/`, put that path into its line of `ports.real.cmd`, and keep
the device in that socket. The NT 20 lines are not in the Windows list (no IOC read them).

## Reply time and the latency timer

An FTDI chip hands a short reply to the computer when its latency timer runs out. The timer is
16 ms by default, on Windows (`LatencyTimer` in `MTPPORT.inf`) and on Linux. Step 5 measures
what that costs. Linux sets it per adapter in
`/sys/bus/usb-serial/devices/ttyUSB<n>/latency_timer` (1 to 255 ms), which one more udev rule
can do. It is not set here: measure first.

## Not known

- Whether the adapter in the rack is the one with the serial number `CO001144`, and whether it
  reports it over USB (assumption A29 in `docs/emulation/STATUS.md`). Windows listed all three
  Matsusada adapters with `1192:1000` and without a serial number, so `/dev/mist2/co-u32` will
  probably not appear. Steps 1 and 3 show it.
- Whether the serial numbers of `99-mist2-serial.rules` are what Linux reports: they are taken
  from Windows' instance IDs, which is the USB serial number string for these devices.
- The USB-OPT: its serial number, and for certain its USB ID. Neither driver package names
  the USB-OPT. Matsusada's current package binds to `1192:1000` and to nothing else, so if it
  is the driver of the USB-OPT (the owner's belief; Matsusada's web site refused an automated
  request, so it was not read there), the USB-OPT reports the same ID and rules 1 and 2 cover
  it already. It then needs one more line like rule 3, with its serial number and the name
  `mist2/usb-opt`. If it shows another ID and holds an FTDI chip, rules 1 and 2 need that ID
  as well. Otherwise: the decision tree in `plan/CO-U32_driver_brief.md`.
- Which FTDI chip the CO-U32 holds. The driver finds that out by itself.
