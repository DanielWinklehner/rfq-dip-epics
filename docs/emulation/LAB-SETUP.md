# MIST-2: first installation on the real computers

Written on 2026-11-24 for the first day with hardware. **Nothing here was run on hardware.**
What was run: the build script (step 2) in fresh containers of Ubuntu 20.04, 22.04 and 24.04,
and both IOCs started there in `real` mode with no device connected. Everything else rests on
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
4. **Install Ubuntu Server 24.04 LTS** for a computer without screen: the ordinary
   installation, not "minimized", with "Install OpenSSH server" ticked. 24.04 is the system
   of the IOC image on which every test ran, and the rule file's syntax was checked with its
   udev version. The server installation brings `tmux` and `lsusb`. After the first start:

   ```bash
   modinfo ftdi_sio | head -1
   ```

   It must print a file name. The USB serial drivers are in the package
   `linux-modules-extra`, which an ordinary installation has; if it is missing:
   `sudo apt install linux-modules-extra-$(uname -r)`.

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

Ubuntu, x86_64, as the user that will run the IOC:

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

Send me `lsb_release -a` of the mini PC (A22).

## 3. Rack computer: the device names

`EPICS/ioc/iocBoot/iocRack/ports.real.cmd` names placeholders (`/dev/mist2/...`, `opta-fc`,
`opta-turbo`). Replace each with the real name before the device is used.

1. **Matsusada adapters.** They get no serial port without the rule file:

   ```bash
   sudo cp rfq-dip-epics/EPICS/ioc/host/99-mist2-matsusada.rules /etc/udev/rules.d/ && sudo udevadm control --reload
   ```

   Plug both adapters in again, then:

   ```bash
   lsusb -d 1192: ; ls -l /dev/mist2/ /dev/serial/by-id/
   ```

   Expected: `1192:1000` for each adapter. Windows remembers three such devices, all without
   a serial number over USB (2026-11-24), so expect no `/dev/mist2/co-u32` and no separate
   names under `by-id`: take each adapter's name from `ls -l /dev/serial/by-path/` (it
   belongs to the USB socket, so keep each adapter in its socket) and put it into the
   `mat_co` and `mat_opt` lines of `ports.real.cmd`. Which adapter is which: plug one in
   at a time.
2. **Read-only first contact**, before any IOC, outputs off:

   ```bash
   rfq-dip-epics/EPICS/ioc/host/matsusada_probe.py /dev/mist2/co-u32 3 4
   ```

   and the same with the USB-OPT's name and `1 2`. It sends queries only, no set command and
   no `REN`, and says for each reply whether it has the form the protocol file expects.
   Compare the values with the front panels. **The status reply must be `#<unit>` and `CO RM`,
   `CF RM`, `CO LO` or `CF LO`:** since T22 every state read checks it (A41). Then once with
   `--repeat 100`: the reply times decide whether the 150 ms reply timeout holds (A6, P52).
3. **Every other serial device:** plug in one at a time, `ls -l /dev/serial/by-id/`, and put
   that name into its line of `ports.real.cmd` (`/dev/serial/by-path/` if two adapters carry
   no serial number). The Optas: their IP addresses in place of the host names.

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
caget -a IOC-RACK:heartbeat interlock_open AU-20P7-3:status:read AU-20P7-3:voltage:read
```

| Device (port) | Line as configured | Read first | Known gap |
|---|---|---|---|
| AU 3, 4 on CO-U32 (`mat_co`); AU 1, 2 on USB-OPT (`mat_opt`) | 9600 8N1 | `AU-20P7-<n>:status:read`, `:voltage:read`, `:current:limit` | A41 reply format; A24 behaviour in local control |
| Interlock box (`AVR11`) | 115200 8N1 | `INTLK:id`, `interlock_open` | firmware, see below |
| Gauge controller (`AVR6`) | 115200, **even** parity as in the lab's `st.cmd` (A10) | `PRESSURE:id`, `PRESSURE:apg:getpressure` | firmware |
| Sensor box (`AVR10`), valve box (`AVR12`) | 115200 8N1 | `SENSOR:id`, `VALVE:id`, `VALVE:s1:get` | firmware |
| nAIM (`AIM`) | 9600 8N1 | `AIM:getpressure`, `AIM:enable` | protocol from INFICON's description (A15, A40) |
| MFC (`MFC`) | 9600 8N1, address 254 | `MFC:getFlow`, `MFC:setSP` | written from a draft (A11, P11) |
| Faraday cup Opta (`FC`), turbo Opta (`TURBO`) | TCP port 5025 | `FC:id`, `TURBO:id` | firmware not known to me, turbo's does not exist (P12, P13): expect INVALID |
| NT 20 (`NT20_1`) | 9600 8N1, listen only | `TURBO1:raw:get` | record format invented (P14): send me what it shows |
| TDK (`TDK`), platform | 19200 8N1, address 6 | `TDK:voltage:read`, `TDK:status:get` | A8 |
| REK (`REK`), platform | 9600 8N1, unit 1 | `matsusada_probe.py <its device> 1` first, then `REK-1:status:read` | A7, A41 |
| Thermocouples (`thermo`), platform | 19200 8N1; the lab's `st.cmd` said 9600 (A9) | `THM:id`, `THM:t1:get` | firmware |

**Firmware of the Arduino boxes.** `<DEVICE>:id` and every valve or relay command need libcom1
protocol 2. A box with the old firmware still gives its readings, but its `:id` is INVALID and
a set is refused and not executed (`AVR/libcom1/README.md`). The sketches are in
`AVR/devices/` (InterlockBox, SolenoidValveBox, SensorBox, IonGaugeController_Teensy) and
`AVR/Thermocouple`. I have not compiled or flashed them.

**If a reply does not match,** the IOC log prints the bytes it got and what it expected. That
line is what I need. A Matsusada status reply in another form means changing the same input
line in eight places of `EPICS/Db/matsusada_co_ctrl.proto` and of `rek.proto`.

**The platform IOC reads `interlock_open` from the rack IOC.** On the platform computer
`caget interlock_open` must answer. If not: `export EPICS_CA_ADDR_LIST=<rack IP>` before
`run-ioc.sh` (Channel Access: UDP 5064 and 5065, TCP 5064).

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

- **Loop service** (platform computer): the commands of `loops/README.md`, "On the platform
  computer" (they make a clone of their own under `/opt/mist2`; not tried on a real
  computer). Check `caget LOOP-DIS:service:get` (1). A start is always MANUAL. Leave
  `LOOP-DIS:mode:setpoint` there until TDK and REK are checked by hand: the gains come from
  the model (A32), tuning is `LOOP.md` section 7.
- **GUI**, on any Linux or WSL2 with Docker Engine:

  ```bash
  cd rfq-dip-epics && git submodule update --init && cp RAS/mist2/env.template RAS/mist2/.env
  ```

  In `RAS/mist2/.env` set `EPICS_CA_ADDR_LIST="<rack IP> <platform IP>"`, then
  `make -C RAS/mist2 dev-up` (15 minutes the first time) and open <http://localhost:3000/>.
  Not tried with IOCs on another computer.
- **Logger:** not needed on the first day. Its home is the main lab computer (Ubuntu, the
  largest disk), as long as that computer stays on whenever the IOCs are on: switch its
  automatic suspend off. `make -C logger up` there, with the same address list and new
  passwords in `logger/.env` (`LOGGER.md` sections 9 and 10).

## 7. What I need back

The probe's output with reply times, `ls -l /dev/serial/by-id/` of both computers,
`lsb_release -a`, both IOC logs, the raw line of the NT 20, your `ports.real.cmd` files, and
every reply that did not match.

Not there yet: udev names for the devices other than the CO-U32, a start of the IOCs at boot
(systemd), and the one-hour acceptance run of the CO-U32 (`plan/CO-U32_driver_brief.md`).
