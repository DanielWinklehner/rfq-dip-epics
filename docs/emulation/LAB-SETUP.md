# MIST-2: first installation on the real computers

Written on 2026-11-24 for the first day with hardware. **Nothing here was run on hardware.**
What was run: the build script (step 2) in fresh containers of Ubuntu 20.04, 22.04, 24.04 and
26.04, and of 32-bit Ubuntu 16.04 and 18.04, and both IOCs started there in `real` mode with
no device connected. Everything else rests on
the emulation. Open assumptions (A..) and points (P..) are in [STATUS.md](STATUS.md).

## 1. Before you start

The plan of 2026-11-24 (yours): nothing runs in the lab, the rack computer's data is copied,
the computer is wiped and gets a fresh Ubuntu, and the devices come back one by one.

**Before the rack computer is wiped**

1. **Save the lab IOC's whole folder** (`st.cmd`, databases, protocol files), beside your own
   data, and the same folder of the mini PC. Together they settle A1, A4 and A7 to A12, and
   the COM numbers in `st.cmd` name the device behind each adapter.
2. **Save the list of the adapters Windows remembers,** also those not plugged in. In
   PowerShell on the rack computer (it reads only):

   ```powershell
   Get-PnpDevice | Where-Object { $_.Class -eq 'Ports' -or $_.InstanceId -match 'VID_' } | Sort-Object Class, FriendlyName | Format-Table -AutoSize Status, Class, FriendlyName, InstanceId | Out-File -Width 300 rack-usb-devices.txt
   ```

   A COM port's name holds its COM number, its instance ID the USB ID and the serial number
   of its adapter: with the lab's `st.cmd` that is the device name of every serial line, and
   the answer to A29 and P34. Run on the development PC, which has no serial adapter: the
   command works and lists devices that are not plugged in; I have not seen a COM port line.
3. **Check the CO-U32 under Linux before Windows is gone.** That Linux drives the adapter is
   read from the driver files and never tried, and this Windows is the one place where the
   adapter is known to work. The main lab computer runs Ubuntu (your word of 2026-11-24), so
   do it there, with the rule file itself:

   ```bash
   git clone -b emulated-iocs https://github.com/DanielWinklehner/rfq-dip-epics.git
   ```

   ```bash
   sudo cp rfq-dip-epics/EPICS/ioc/host/99-mist2-matsusada.rules /etc/udev/rules.d/ && sudo udevadm control --reload
   ```

   Plug the adapter in, then:

   ```bash
   lsusb -d 1192: ; ls -l /dev/mist2/ /dev/serial/by-id/ ; sudo dmesg | tail -5
   ```

   Expected: `1192:1000` and "FTDI USB Serial Device converter now attached to ttyUSB0". If
   so, wipe. If not, keep Windows (or its disk) and send me the output.
   `/dev/mist2/co-u32` will probably **not** appear: the list of devices Windows remembers
   (2026-11-24) shows the Matsusada adapters without a serial number over USB, three times
   under names made from the USB socket. Then the rule file's name by serial number cannot
   work, and the adapter is named by its socket: `ls -l /dev/serial/by-path/`. Send me that
   line and `udevadm info -q property -n /dev/ttyUSB0`. This shows that the adapter gets its serial port. That the supplies answer through
   it needs a powered supply on the fiber, outputs off, and the probe of section 3, which
   runs there as well (Python 3, no IOC).
4. **The computers as installed** (your word of 2026-11-24): Ubuntu 26.04.1, the desktop
   installation, on the rack server and on the lab computer; the platform computer stays on
   its older 32-bit Linux. On a desktop installation three things are not as a computer
   without screen needs them:

   ```bash
   sudo apt install openssh-server tmux
   ```

   ```bash
   sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
   ```

   ```bash
   sudo systemctl disable --now ModemManager
   ```

   The first gives SSH and `tmux` (step 4). The second stops the computer from going to
   sleep when nobody uses it: do it on the rack server (the IOC) and on the lab computer (the
   logger). The third: ModemManager, installed with the desktop, is known to send modem
   commands to Arduino serial ports when they appear; I have not checked that on 26.04, and
   neither computer has a modem. Then:

   ```bash
   modinfo ftdi_sio | head -1
   ```

   It must print a file name. On 26.04 the USB serial drivers are in the kernel's standard
   package (`linux-modules`), read from the package, not from an installed computer.
   Both rule files pass the syntax check of its udev (systemd 259).

**On the day**

- **One IOC per computer.** The new IOCs serve the same PV names as the lab's, and a serial
  line takes one master. If the mini PC still holds the lab's IOC, see that it does not
  start at boot.
- **Outputs off** at all supplies. Doors open is fine: it keeps the permit away.
- **The interlock box comes before any high voltage.** Without it `interlock_open` is INVALID
  and no AU or REK output can be switched on.
- **Current limits first.** `EPICS/ioc/iocBoot/iocRack/limits.defaults` and
  `iocHV/limits.defaults` hold the full scales (15, 7.5, 7.5, 7.5 mA, 24 A). At its first
  contact the IOC sends each Matsusada supply `REN` and this limit. Put your limits in before
  the first start.
- What an IOC start does by itself: it reads, it sends `REN` and the current limit to each
  Matsusada supply (AU and REK), and it takes over the state it finds. It switches nothing
  on. A Matsusada supply that is on is switched off while `interlock_open` is 1 or INVALID
  (the interlock box not answering counts).
- Both computers need the internet for step 2, and the same subnet afterwards.

## 2. Build, on each of the two IOC computers

As the user that will run the IOC. On Ubuntu 26.04 take the script of 2026-11-24 evening or
later (`git pull`): before that it stopped in StreamDevice, which the compiler of 26.04 does
not accept without a flag. On the 32-bit platform computer the same commands build for
`linux-x86`; `run-ioc.sh` finds that build by itself. If its `apt` no longer finds the
packages (an old release), send me what it says.

```bash
sudo apt install build-essential perl git ca-certificates libreadline-dev libtirpc-dev
```

```bash
git clone -b emulated-iocs https://github.com/DanielWinklehner/rfq-dip-epics.git
```

```bash
sudo mkdir -p /opt/epics && sudo chown "$USER": /opt/epics
```

```bash
rfq-dip-epics/EPICS/ioc/host/build-epics.sh
```

```bash
sudo usermod -aG dialout "$USER"
```

Log in again after the last one. The script builds EPICS base R7.0.10, asyn, StreamDevice,
autosave and the IOC: about 2 minutes on the 28-core development PC, so expect a quarter of an
hour or more on a small PC. A second run goes on where the first stopped. Then, in every
terminal you use:

```bash
export PATH=/opt/epics/base/bin/linux-x86_64:$PATH
```

(`linux-x86` in place of `linux-x86_64` on the 32-bit computer: the script prints the line.)

Send me `lsb_release -a`, `uname -m`, `gcc --version` and `python3 --version` of the platform
computer (A22).

## 3. Rack computer: the device names

`EPICS/ioc/iocBoot/iocRack/ports.real.cmd` names `/dev/mist2/...` and `opta-turbo`. Four of
those names come from a rule file by serial number (step 3); replace every other one with the
real name before the device is used.

1. **Matsusada adapters.** They get no serial port without the rule file. Seen on the rack
   server on 2026-11-24: both report `1192:1000`, the kernel's driver takes them, and neither
   reports a serial number, so the rule file names them by their USB socket. Copy the rule
   file again (it changed that day), then pull both adapters and plug them into the same
   sockets:

   ```bash
   sudo cp rfq-dip-epics/EPICS/ioc/host/99-mist2-matsusada.rules /etc/udev/rules.d/ && sudo udevadm control --reload
   ```

   ```bash
   ls -l /dev/mist2/
   ```

   Expected: `co-u32` (the line on which units 3 and 4 answered, socket 1.2) and `usb-opt`
   (units 1 and 2, socket 1.1). `ports.real.cmd` opens these two names, so it needs no edit
   for them. Seen to work on the rack server on 2026-11-24. If one is missing (an adapter in
   another socket), send me `udevadm info -q property -n /dev/ttyUSB0 | grep ID_PATH`.
2. **First contact without an IOC**, outputs off. Read-only:

   ```bash
   rfq-dip-epics/EPICS/ioc/host/matsusada_probe.py /dev/mist2/co-u32 3 4
   ```

   and the same with `/dev/mist2/usb-opt 1 2`. Seen on 2026-11-24, with the supplies under
   local control: the status reply has the form the protocol files check (`#3 CF LO`), the
   monitors answer, a reply is complete after 31 to 35 ms, and the settings (`SW?`, `CH0?`,
   `CH1?`) are **not** answered. Under remote control, as the IOC uses the supplies:

   ```bash
   rfq-dip-epics/EPICS/ioc/host/matsusada_probe.py /dev/mist2/co-u32 3 4 --remote
   ```

   This sends `REN` to each unit, asks the same six queries, sends `GTL` (back to the front
   panel) and asks the status once more. Neither command sets a voltage, a current or the
   output. All six must answer now; the IOC needs the three settings. Seen on 2026-11-24:
   all four supplies answer all six under remote control and are back under local control
   after `GTL`. Their stored current limit was 0 (`CH1=0000H`): the IOC sends the limit of
   `limits.defaults` at its first contact.
3. **The devices with a serial number** (Windows' list of 2026-11-24 with the lab's `st.cmd`,
   `reference/lab-2026`): gauge controller, interlock box, valve box and MFC get their names
   from `99-mist2-serial.rules`:

   ```bash
   sudo cp rfq-dip-epics/EPICS/ioc/host/99-mist2-serial.rules /etc/udev/rules.d/ && sudo udevadm control --reload
   ```

   Plug them in, then `ls -l /dev/mist2/`: `gauges`, `interlock`, `valves`, `mfc`. A missing
   one: `udevadm info -q property -n /dev/ttyACM0` (or `ttyUSB0`) shows the serial number
   Linux reads; send it to me. Table and sources: `EPICS/ioc/host/README.md`.
4. **Every other serial device** (nAIM, the Faraday cup Opta, the flow meter Opta, the NT 20
   lines; Windows saw no serial number for the first three): plug in one at a time,
   `ls -l /dev/serial/by-path/`, put that name into its line of `ports.real.cmd`, and keep the
   device in that socket. The turbopump Opta: its IP address in place of the host name.

## 4. Start and look

Rack computer:

```bash
rfq-dip-epics/EPICS/ioc/iocBoot/run-ioc.sh iocRack real
```

Platform computer, after `ports.real.cmd` of `iocHV` has its three names:

```bash
rfq-dip-epics/EPICS/ioc/iocBoot/run-ioc.sh iocHV real
```

Over SSH, start each IOC inside `tmux`, or it ends with the connection:

```bash
tmux new -s ioc
```

Ctrl-b d leaves it running, `tmux attach -t ioc` comes back to it.

The terminal is the IOC shell and the log; `exit` stops the IOC. A device that is missing
costs log lines only, its PVs are INVALID and the IOC runs. After a device was connected for
the first time, or a port file changed, restart the IOC. Read with alarm state from a second
terminal:

```bash
caget -a IOC-RACK:heartbeat interlock_open AU-20P7-3:status:read AU-20P7-3:voltage:read AU-20P15-1:status:read
```

| Device (port) | Line as configured | Read first | Known gap |
|---|---|---|---|
| AU 3, 4 on CO-U32 (`mat_co`); AU 1, 2 on USB-OPT (`mat_opt`) | 9600 8N1 | `AU-20P15-1:` (the source supply, the lab's name) and `AU-20P7-<n>:` (2, 3, 4) `status:read`, `:voltage:read`, `:current:limit` | A41 reply format; A24 behaviour in local control; the lab's `st.cmd` puts units 2, 3, 4 on one line and 1, 5 on the other (question 18) |
| Interlock box, an Opta now (`AVR11`) | USB serial | `INTLK:id` (InterlockOpta), `interlock_open` | "The interlock box is an Opta", below |
| Gauge controller (`AVR6`) | 115200, **even** parity as in the lab's `st.cmd` (A10) | `PRESSURE:id`, `PRESSURE:apg:getpressure` | firmware |
| Valve box (`AVR12`) | 115200 8N1 | `VALVE:id`, `VALVE:s1:get` | firmware |
| Flow meter Opta (`AVR23`, the lab's COM23) | 115200 8N1 | `FLOW:f1:getflow` to `FLOW:f5:getflow` (l/min) | which circuit each is (question 18 c); no identity records (protocol 1) |
| nAIM (`AIM`) | 9600 8N1 | `AIM:getpressure`, `AIM:enable` | protocol from INFICON's description (A15, A40) |
| Foreline gauge, INFICON VGC401 (`VGC`) | 9600 8N1, the controller's default | `PRESSURE:foreline:getpressure`, `:getstate`, `:getgauge`, `:getunit` | never run on the controller (A51): "The foreline gauge and the TIC", below |
| Edwards TIC station (`TIC`) | 9600 8N1, Xon/Xoff | `TIC:variant:get`, `TIC:gauge1:getpressure`, `TIC:turbo:state:get` | never run on the controller, variant not known (A52, question 23) |
| MFC (`MFC`) | 9600 8N1, address 254 | `MFC:getFlow`, `MFC:setSP` | written from a draft (A11, P11) |
| Faraday cup Opta (`AVR16`, the lab's COM16) | 115200 8N1 | `FC1:i1:getcurrent`, `FC1:i2:getcurrent` | what i1 and i2 are and their unit, the sketch (question 18 b); no identity records (protocol 1) |
| Turbo Opta (`TURBO`) | TCP port 5025 | `TURBO:id` | firmware does not exist (P13): expect INVALID |
| NT 20 (`NT20_1`) | 9600 8N1, listen only | `TURBO1:raw:get` | record format invented (P14): send me what it shows |
| TDK (`TDK`), platform | 19200 8N1, address 6 | `TDK:voltage:read`, `TDK:status:get` | A8 |
| REK (`REK`), platform | 9600 8N1, unit 1 | `matsusada_probe.py <its device> 1` first, then `REK-1:status:read` | A7, A41 |
| Thermocouples (`thermo`), platform | 19200 8N1; the lab's `st.cmd` said 9600 (A9) | `THM:id`, `THM:t1:get` | firmware |

**Firmware of the Arduino boxes.** The boards as last flashed speak libcom1 **protocol 1**: the
Arduino library on the rack computer had no protocol 2 (`reference/lab-2026/README.md`). They
give their readings (query `A`), but answer identity and acknowledged sets with `ERR0`. So
`<DEVICE>:id` is INVALID and every valve or relay command is refused and not executed
(`AVR/libcom1/README.md`) until a box is flashed with protocol 2. The sketches of this branch
are in `AVR/devices/` (InterlockOpta, SolenoidValveBox, IonGaugeController_Teensy; InterlockBox
is the lost box's, SensorBox is no longer used) and `AVR/Thermocouple`, with the rack computer's
local changes (same pins). The valve box sketch and the old interlock box sketch compile for the
Arduino Mega 2560, the new interlock sketch for the Opta, all with one command in a container
(`AVR/tools/compile.sh`, fixed versions of Arduino's tools); the others I have not compiled, and
none is flashed by me. The two Optas in use need only `A` and get no identity records:
the flow meter sketch, protocol 1, is in `reference/lab-2026/AVR/devices/FlowMeters`; the
Faraday cup Opta's sketch is not known.

**Flashing a box with the Arduino IDE** (the valve box as the example):

1. No program may have the box's serial port open: stop the IOC on that computer first.
2. The IDE needs two libraries of this repository in its sketchbook:

   ```bash
   mkdir -p ~/Arduino/libraries && cp -r rfq-dip-epics/AVR/libcom1 rfq-dip-epics/AVR/libutil ~/Arduino/libraries/
   ```

3. Open `rfq-dip-epics/AVR/devices/SolenoidValveBox/SolenoidValveBox/SolenoidValveBox.ino`,
   board "Arduino Mega or Mega 2560", the box's port, then Verify and Upload.
4. In the IDE's serial monitor (115200 baud, line ending "Newline"): `I` must answer with
   `oID=SolenoidValveBox;FW=...;PROTO=2;CH=s1,...,s8`, `A` with eight values, and `Ss51` with
   `ok` while relay 5 switches (`Ss50` switches it back). Channels 5 to 8 are unused; 1 to 4
   are the foreline valve, the MFC shut-off, the vent valve and the Faraday cup.
5. Close the serial monitor, start the IOC, then `caget -a VALVE:id VALVE:firmware VALVE:s1:get`
   and, for the first set through the IOC, `caput VALVE:s5:set 1` and `caput VALVE:s5:set 0`.

The sketch sets no communication timeout: the valves keep their state when the IOC stops, and
the IOC sends nothing at its start (it takes over the state it reads). What can release all
eight relays is a restart of the Arduino Mega itself, which happens when the DTR line of its
port goes from off to on:

- **The first IOC start after the box was plugged in or the rack server booted:** the box
  restarts, all relays released.
- **Every later IOC restart:** no restart of the box expected. The IOC's serial driver leaves
  DTR on when it closes the port, so the next start makes no edge. Seen for the driver's
  setting on a pseudo-terminal, not yet on the box: switch relay 5 on, restart the IOC, and the
  relay should stay on with `VALVE:s5:set` and `VALVE:s5:get` both 1.
- **The Arduino IDE or its serial monitor on this port:** restarts the box.

To keep the relays through a warm reboot of the server as well, the Mega's automatic reset has
to be disabled on the board (the solder bridge RESET-EN cut); flashing then needs the reset
button. Not done, not needed for IOC restarts.

The relays are SRD-05VDC-SL-C (5 V coil), and the relay board has its own supply cable: USB
feeds only the Arduino. The firmware before this one is `AVR/devices/SolenoidValveBox` at
commit `3790bda` of `master`.

**The interlock box is an Opta** (your third one; the old box was not found). The sketch is
`AVR/devices/InterlockOpta`, and its `README.md` has the wiring table, the limits from the data
sheet and the full check list. The IOC needs no change: same port, same PVs. **The sketch is
compiled and tested on a PC and has never run on an Opta**, so the bench comes first.

It is not personnel protection: it reports the doors to the IOC and gives a contact that
follows them.

1. **Wiring.** The Opta's supply terminals on the +24 V rail of the NIM crate, as the other
   two Optas, and USB to the rack computer (owner, 2026-11-25). Both are needed: USB alone
   does not power the relays. Each door switch between that same +24 V and one input: door 1
   on I1, door 2 on I2. An input reads "closed" from 6.6 V and takes up to 24 V. On the bench
   a wire from plus to I1 and I2 stands in for the switches.
   The crate is part of the interlock from then on: with the crate off no input is high and
   no relay has power, so the doors read as open (or the box does not answer at all) and the
   IOC keeps the AU supplies and the REK off. Expected from the wiring, not seen.
2. **Flash** with the Arduino IDE 2, as the valve box, with these differences: in the Boards
   Manager install "Arduino Mbed OS Opta Boards" (this repository compiles with 4.6.0), board
   "Opta". Copy `AVR/libcom1` and `AVR/libutil` again from a fresh `git pull` into the
   sketchbook's `libraries` folder, the old `libcom1` there deleted first. Open
   `AVR/devices/InterlockOpta/InterlockOpta.ino`; its two headers must stay beside it.
3. **Serial monitor** (line ending "Newline", any baud rate except 1200, which sends the Opta
   into its bootloader): `I` must answer `oID=InterlockOpta;FW=...;PROTO=2;CH=i1,i2,s1,s2`.
   `A` answers `o0:0:0:0` with nothing on the inputs, and `o1:1:0:0` once both inputs have been
   at plus for a second: relays 1 and 2 click, their lamps and the green lamp come on. Take one
   wire off: `A` shows that door as 0 at once and the relays drop; put it back and it takes a
   second.
4. **Three things only the bench can show.** Tell me each result.
   - **24 V alone:** unplug USB, then take the plus wire off the Opta's supply terminal and
     put it back, with both inputs at plus (not the crate's switch: the other Optas hang on
     it). Relays 1 and 2 must come on after about a second, without a computer.
   - **A second flash:** upload the sketch once more while it runs. If the upload fails or the
     board restarts in the middle, that is the watchdog (the sketch's README says what to do).
   - **USB pulled while the IOC reads:** with the IOC running and both inputs at plus, pull the
     USB cable, then take one wire off an input. Relay 1 must drop at once. If it takes seconds,
     tell me: the sketch then needs a change before its contacts are used for anything (P62).
5. **The name for the IOC.** With the Opta plugged into the rack server, send me the output of

   ```bash
   for d in /dev/ttyACM*; do echo "$d"; udevadm info -q property -n "$d" | grep -E "ID_VENDOR_ID|ID_MODEL_ID|ID_SERIAL_SHORT|ID_PATH="; done
   ```

   and I add its line to `99-mist2-serial.rules` (the line there is still the lost box's).
   Until then the name under `/dev/serial/by-path/` in the `AVR11` line of `ports.real.cmd`
   works as well.
6. **With the IOC:**

   ```bash
   caget -a INTLK:id INTLK:i1:get_interlock INTLK:i2:get_interlock interlock_open
   ```

   `interlock_open` must be 0 without alarm while both inputs are at plus, and 1 with a wire off.

**If a reply does not match,** the IOC log prints the bytes it got and what it expected. That
line is what I need. A Matsusada status reply in another form means changing the same input
line in eight places of `EPICS/Db/matsusada_co_ctrl.proto` and of `rek.proto`.

**The platform IOC reads `interlock_open` from the rack IOC.** On the platform computer
`caget interlock_open` must answer. If not: `export EPICS_CA_ADDR_LIST=<rack IP>` before
`run-ioc.sh` (Channel Access: UDP 5064 and 5065, TCP 5064).

### The foreline gauge and the TIC

Both are read only: the IOC asks for readings and sends no setting and no command (tasks T29 and
T30, `docs/emulation/VGC401.md`, `docs/emulation/TIC.md`). **Neither has met its controller.**
Each has a probe that runs without an IOC; run it first and send me its output.

1. **Probe**, with the controller's serial socket on a USB to RS-232 adapter (a straight cable
   for both, by their manuals), on whichever computer the adapter is plugged into. Two things
   first, both seen on the lab computer on 2026-11-25: the user must be in the group `dialout`
   (`sudo usermod -aG dialout "$USER"`, then log in again), or the port cannot be opened; and
   the desktop's ModemManager must keep off the port, because any character it sends ends the
   VGC401's own sending. The rule file does that for the VGC401's adapter (step 2); otherwise
   `sudo systemctl disable --now ModemManager`.

   ```bash
   python3 EPICS/ioc/host/inficon_vgc401_probe.py /dev/ttyUSB0
   ```

   ```bash
   python3 EPICS/ioc/host/edwards_tic_probe.py /dev/ttyUSB0
   ```

   The VGC401's probe listens for 3 s first: a controller that was just switched on sends its
   reading every second by itself, and those lines prove cable and baud rate. Its first request
   ends that sending until the controller is switched off and on, and reading the error word
   clears it (both from the manual). The TIC's probe tells which TIC variant it is, what is on
   its three gauge sockets and which pumps it knows.
2. **For the IOC the adapter must be on the rack server.** The VGC401's adapter (FTDI, serial
   number FTE7S80M) gets the name `/dev/mist2/vgc401` from `99-mist2-serial.rules` on any
   computer that has the rule file (copy it again as in section 3, then pull the adapter and
   plug it in; the line is new and not tested). The TIC's adapter has no rule yet: plug it in
   alone, `ls -l /dev/serial/by-path/`, and put that name into the `TIC` line of
   `EPICS/ioc/iocBoot/iocRack/ports.real.cmd` in place of `/dev/mist2/tic`.
   A baud rate other than 9600 on the VGC401 goes into its block of the same file.
3. **Read**, after an IOC restart:

   ```bash
   caget -a PRESSURE:foreline:getpressure PRESSURE:foreline:getstate PRESSURE:foreline:getgauge PRESSURE:foreline:getunit
   ```

   ```bash
   caget -a TIC:variant:get TIC:gauge1:getpressure TIC:gauge1:state:get TIC:turbo:state:get TIC:turbo:speed:get TIC:backing:state:get
   ```

   Pressures are in torr. Below its range the VGC401's value stays, with a MINOR alarm and the
   state "Underrange". A TIC socket without a gauge, and a pump the TIC does not have, are
   INVALID, and the state PV says why.

## 5. First high voltage

Only when `caget -a interlock_open` shows 0 without alarm and the limits are yours. One supply
at a time, wait 5 s after its first answer (P29):

```bash
caput AU-20P7-3:voltage:setpoint 100
```

```bash
caput AU-20P7-3:SetToggleOutput 1
```

Compare `AU-20P7-3:voltage:read` and `:current:read` with the front panel, then
`caput AU-20P7-3:SetToggleOutput 0`. Open a door with an output on: the output must go off
and stay off after the door closes. All four AU off at once: `caput AU:alloff:set 1`.

## 6. Loop service, GUI, logger

- **Loop service:** it needs Python 3.8 or later, which an old 32-bit Linux will not have
  (`python3 --version`). Then run it on the rack server instead: the commands of
  `loops/README.md`, "On the platform computer", there, with the platform computer's address
  in place of `127.0.0.1` in `loops/systemd/mist2loop.service` (`EPICS_CA_ADDR_LIST`). It
  only talks to the platform IOC over the network, and the IOC holds the loop in MANUAL by
  itself while it does not hear the service. Its unit tests pass on the Python 3.14 of 26.04;
  the installation is not tried on a real computer. Check `caget LOOP-DIS:service:get` (1). A start is always MANUAL. Leave
  `LOOP-DIS:mode:setpoint` there until TDK and REK are checked by hand: the gains come from
  the model (A32), tuning is `LOOP.md` section 7.
- **GUI**, on any Linux or WSL2 with Docker Engine. On Ubuntu 26.04 Docker comes from Ubuntu's
  own packages: `sudo apt install docker.io docker-compose-v2 docker-buildx make`, then
  `sudo usermod -aG docker "$USER"` and log in again (not tried on 26.04):

  ```bash
  cd rfq-dip-epics && git submodule update --init && cp RAS/mist2/env.template RAS/mist2/.env
  ```

  In `RAS/mist2/.env` set `EPICS_CA_ADDR_LIST="<rack IP> <platform IP>"`, then
  `make -C RAS/mist2 dev-up` (15 minutes the first time) and open <http://localhost:3000/>.
  Seen on 26.04.1 by the lab session (2026-11-25): `docker-buildx` is only suggested by
  `docker.io`, and the GUI's Compose file builds with `additional_contexts`, so it is in the
  command above (whether the build works without it was not tried); and a new group takes
  effect only after a new login.
  Not tried with IOCs on another computer.
- **Logger:** not needed on the first day. Its home is the main lab computer (Ubuntu, the
  largest disk), as long as that computer stays on whenever the IOCs are on: switch its
  automatic suspend off. `make -C logger up` there, with the same address list and new
  passwords in `logger/.env` (`LOGGER.md` sections 9 and 10).

## 7. What I need back

The probe's output with reply times, `ls -l /dev/serial/by-id/` of both computers,
`lsb_release -a`, both IOC logs, the raw line of the NT 20, your `ports.real.cmd` files, and
every reply that did not match.

Not there yet: udev names for the devices without a serial number (they are named by socket), a start of the IOCs at boot
(systemd), and the one-hour acceptance run of the CO-U32 (`plan/CO-U32_driver_brief.md`).
