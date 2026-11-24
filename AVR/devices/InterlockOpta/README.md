# InterlockOpta

**This box is not personnel protection.** It is a microcontroller with a program, without a
safety rating. For the protection of people the door switches have to break the supplies' own
interlock input or their mains directly, with hard-wired safety relays (`plan/controls.yaml`,
section `interlock`, layer A). This box reports the doors to the IOC and gives a contact that
follows them; nothing more.

Firmware for an Arduino Opta RS485 (AFX00001) that takes the place of the lost interlock box
(an Arduino Mega with `AVR/devices/InterlockBox`). The IOC talks to it exactly as to the old box:
same port (AVR11, USB serial, 115200 8N1), same four channels, same database
(`EPICS/Db/interlockbox.db`), same PV names. Only the identity changes: `INTLK:id` reads
`InterlockOpta` instead of `InterlockBox`.

**Status: compiled for the Opta, tested on a PC. It has never run on an Opta.** The first run is
on your bench (section "First check").

## What the box does

- **Two door inputs.** Terminal I1 is door 1 (channel `i1`), I2 is door 2 (`i2`). A door counts
  as closed while its input is high (ASSUMED, see "Which way the switches work").
- **Hold time.** When an input reads open, that door is reported open at once. It is reported
  closed again only after its input has read closed **without interruption for 1 s**
  (`HOLD_MS`). The IOC reads the box ten times a second and switches the supplies off when it
  sees an open door; with the hold time an opening of a millisecond, or a bouncing switch, is
  still reported for at least 1 s and reaches the IOC. After power-on both doors are reported
  open for the first second.
- **Interlock contacts.** Relays 1 and 2 are on (contact closed) only while both doors are
  reported closed. This is decided in the Opta, without the IOC: no command over the line can
  switch them (tested with every command against every channel name and 40 000 random lines).
  They are off after power-on and after a restart.
- **No latch.** When both doors are closed again (after the hold time) relays 1 and 2 come back
  on by themselves, as the old box's outputs did. The IOC latches the supplies: they stay off
  until the operator switches them on again. Whether the contact itself must latch is a question
  for you (see "Open questions").
- **Two spare relays.** Relays 3 and 4 are the old box's channels `s1` and `s2`: a set of exactly
  1 switches on, any other number off, and they read back 1 or 0. No database uses them. They
  have nothing to do with the doors.
- **A set of `i1` or `i2` is accepted and does nothing**, as in the old box.
- **No communication timeout.** The box works the same whether or not the IOC talks to it.
- **Watchdog.** The processor's hardware watchdog restarts the sketch when it hangs for 8 s
  (`WATCHDOG_MS`); a restart switches all relays off, and the doors are reported open for the
  first second after it.
- **Lamps.** STATUS 1 to 4 light with relays 1 to 4. The lamp on the RESET button is green while
  both doors are reported closed and red while a door is reported open. The Opta RS485 has no
  USER lamp (that one is on the WiFi variant only), so it is not used.

## Terminals and wiring

| Terminal | Connect | Notes |
| --- | --- | --- |
| Supply `+` / `-` (two of each) | 12 to 24 V DC | The relays work only with this supply: USB alone does not power them. |
| I1 | door switch 1: one side to supply `+`, the other to I1 | high (closed door) above 6.6 V, low below 4.46 V |
| I2 | door switch 2: one side to supply `+`, the other to I2 | as I1 |
| Relay 1 (two terminals, NO contact) | interlock contact 1 | closed while both doors are reported closed |
| Relay 2 (two terminals, NO contact) | interlock contact 2 | the same as relay 1, a second independent contact |
| Relay 3 | spare (`s1`) | switched by command only |
| Relay 4 | spare (`s2`) | switched by command only |
| USB-C | rack computer | the IOC's port AVR11 |
| I3 to I8, RS-485, Ethernet | nothing | |

Each switch is fed from the Opta's own supply, so that a broken wire, a switch that has come off
its terminal or a missing supply all read low, which is an open door. The input reads against the
supply's `-` terminal: ASSUMED, the documents I read give the thresholds but do not name the
reference terminal in words.

### Which way the switches work (ASSUMED)

The owner has not yet said whether the switches close or open when the door closes (STATUS.md,
A48). The sketch assumes they **close when the door closes**, as the old box read them (both
inputs high = interlock closed). The level is one constant per input in `interlock_device.hpp`:
`DOOR1_CLOSED_LEVEL`, `DOOR2_CLOSED_LEVEL` (`true` = high is closed).

Do not set them to `false` to fit a switch that opens when the door closes: a broken wire, a
loose terminal or a missing supply also reads low, and with `false` that counts as a **closed**
door. The fail-safe way with such a switch is its other contact (most door switches have an NC
and an NO contact), or a relay that turns it round.

## Electrical limits

From the datasheet "Arduino Opta Collective Datasheet", SKU AFX00001-AFX00002-AFX00003,
<https://docs.arduino.cc/resources/datasheets/AFX00001-AFX00002-AFX00003-datasheet.pdf>
(revision 12, modified 19/11/2026, read on 2026-11-24), and the Opta user manual
<https://docs.arduino.cc/tutorials/opta/user-manual> (its source, `content/hardware/opta/opta-family/opta/tutorials/01.user-manual/content.md`
in github.com/arduino/docs-content, commit 8fd71db of 2026-11-02, read on 2026-11-24):

| What | Value | Where |
| --- | --- | --- |
| Variant | AFX00001 = Opta RS485 (AFX00003 Lite, AFX00002 WiFi) | datasheet, variant table; user manual, "Opta Variants" |
| Supply voltage | 12 to 24 V DC; permissible range 10.2 to 27.6 V | datasheet 4.2 "Power Specification" |
| Power consumption | 0.6 to 2 W at 12 V, 0.6 to 2.2 W at 24 V | datasheet 4.2 |
| Digital input voltage | 0 to 24 V | datasheet 3.5.2; user manual "Digital Inputs" |
| Reads low / high | low at most 4.46 V, high at least 6.6 V | datasheet 3.5.2 (revision 9 "Digital input specification update") |
| Input current, impedance | 1.12 mA at 10 V; 8.9 kOhm | datasheet 3.5.2 and 3.5 |
| Input overvoltage protection | yes | datasheet 3.5 |
| Relay contact | normally open (NO), single pole (SPST) | datasheet 3.6 and terminal list (3F) |
| Relay current | 10 A continuous, 15 A peak | datasheet 3.6 |
| Relay voltage | rated 250 V AC, maximum 400 V AC | datasheet 3.6, 5.9 |
| Relay rated load | AC1 2500 VA, AC15 (230 V AC) 500 VA | datasheet 3.6, 5.9 |
| Relay DC breaking capacity (DC1) | 10 A at 24 V, 4 A at 30 V, 0.3 A at 110 V, 0.12 A at 220 V | datasheet 3.6, 5.9 |
| **Relay minimum load** | **300 mW, 5 V, 5 mA** | datasheet 5.9 |
| Relay response | 6 ms on, 4 ms off | datasheet 3.6 |
| Lamps | STATUS 1 to 4 = `LED_D0`..`LED_D3`; USER (`LED_USER`) WiFi variant only; RESET green `LEDG`, RESET red `LEDR` | user manual "LEDs" |

The minimum load matters here: the Opta's relays are power relays, and all three numbers hold
together. In the datasheet's words (5.9): "with 5 V the current must be at least 60 mA, with
24 V, it must be at least 12.5 mA, and with 5 mA the voltage must be at least 60 V". An interlock
input of a supply that carries a few milliamperes at 5 to 24 V is below that and is not switched
reliably by these contacts; it would need a small signal relay in between. What the supplies'
interlock inputs carry is not known here.

Not read: the full pinout PDF <https://docs.arduino.cc/resources/pinouts/opta-full-pinout.pdf>
(the server returned an HTML page, not the PDF). The user manual page itself renders with
JavaScript only; I read its source on GitHub.

## Flashing (Arduino IDE 2, Windows 11 or Ubuntu)

1. **Board package.** Tools > Board > Boards Manager, search `opta`, install
   **Arduino Mbed OS Opta Boards** (user manual, "Opta Core and Libraries"). This repository's
   compile uses version **4.6.0**; take that one if the IDE offers a choice.
2. **Libraries.** Copy the two folders `AVR/libcom1` and `AVR/libutil` of this repository into the
   `libraries` folder of your sketchbook (its location is shown under File > Preferences >
   Sketchbook location; restart the IDE afterwards).
   Take them from a checkout of 2026-11-25 or later. Before that, `libcom1/examples/StandaloneExample`
   held symbolic links back to `libcom1`, and arduino-cli 1.5.1, which the IDE uses, then refused
   the whole library ("directories symlink loop detected", followed by
   `libcom1.hpp: No such file or directory`). If the IDE says that, delete the old `libcom1` in
   the sketchbook and copy it again.
3. **Sketch.** Open `AVR/devices/InterlockOpta/InterlockOpta.ino`. The two headers beside it
   (`door_logic.hpp`, `interlock_device.hpp`) open as tabs and must stay in the same folder.
4. **Board.** Tools > Board > Arduino Mbed OS Opta Boards > **Opta**. Leave the menus at their
   defaults: Target core "Main Core", Flash split "2MB M7", Security setting "None"
   (`boards.txt` of the core). The fqbn is `arduino:mbed_opta:opta`.
5. **Port.** Connect the USB-C cable, choose its port, Upload.

What happens to the relays during a flash: the IDE opens the port at 1200 baud, the board
restarts into its bootloader (`USBSerial.cpp` and `_ontouch1200bps_()` in `variant.cpp` of the
core), the sketch stops. **Count on the interlock contacts being open from that moment until the
new sketch has run for 1 s.** What the relay outputs actually do while the bootloader runs is not
known (the bootloader is a binary).

The watchdog and a flash: once started the watchdog cannot be stopped, and "a software reset may
not stop the watchdog timer; the behavior is platform specific" (`hal/watchdog_api.h` of the
core). The bootloader shipped with the core (`bootloaders/OPTA/bootloader.elf`) has no watchdog
function in its symbol table. If the watchdog keeps running into the bootloader, the bootloader
would be restarted 8 s after the board entered it. **Not known** whether that happens. If an
upload fails or the board restarts during it: unplug the USB cable and the 24 V supply, plug the
USB cable in again, then retry. Forum posts (not Arduino's documentation) say a double press of
the RESET button keeps the board in its bootloader. As a last resort, set `WATCHDOG_MS` to 0 for
one flash.

## First check with the serial monitor

Without the IOC (only one program can have the port open). Serial monitor: line ending
**Newline**; the baud rate is not used by the USB port, but **never choose 1200** (that restarts
the board into its bootloader). Supply the Opta with 24 V.

| Type | With | Must come back |
| --- | --- | --- |
| `I` | | `oID=InterlockOpta;FW=<build date>;PROTO=2;CH=i1,i2,s1,s2` |
| `A` | nothing on I1, I2 | `o0:0:0:0` (doors open, spare relays off); red lamp on, STATUS 1, 2 dark |
| `A` | I1 and I2 at supply `+` (doors closed) for more than 1 s | `o1:1:0:0`; relays 1, 2 click, STATUS 1, 2 and the green lamp on |
| `A` | I1 taken off `+` | `o0:1:0:0` at once; relays 1, 2 off, red lamp |
| `A` | I1 back on `+`, asked within 1 s | still `o0:1:0:0`; after 1 s `o1:1:0:0` |
| `Ss11` | | `ok`; relay 3 and STATUS 3 on; `gs1` gives `o1` |
| `Ss10` | | `ok`; relay 3 off |
| `Si10` | doors closed | `ok`, and `A` still gives `o1:1:...` (a set of a door does nothing) |
| `gx1` | | `ERR4` (no such channel) |

Values are written as `%g` (`1`, `0`), not in the old box's AVR format (`+1.e+00`); the IOC
reads both (`EPICS/Db/libcom1.proto`: `in "o%g"`).

Then check with a meter that each interlock contact (relay 1, relay 2) opens when either door
opens, and with a wire taken off each switch.

## Constants

| Constant | File | Value | Meaning |
| --- | --- | --- | --- |
| `HOLD_MS` | `interlock_device.hpp` | 1000 | an input must read closed this long, without interruption, before its door is reported closed |
| `DOOR1_CLOSED_LEVEL`, `DOOR2_CLOSED_LEVEL` | `interlock_device.hpp` | `true` | input level of a closed door (ASSUMED, see above) |
| `WATCHDOG_MS` | `InterlockOpta.ino` | 8000 | watchdog time; 0 = no watchdog; limited to `Watchdog::get_max_timeout()` |
| `IDENTITY` | `interlock_device.hpp` | `InterlockOpta` | reported by `I`; the firmware version is `__DATE__` |
| `OUT_BUFFER`, `IN_BUFFER` | `interlock_device.hpp` | 128, 128 | as in the old box |

## The code

- `door_logic.hpp`: the decision (doors, hold time, relays 1 and 2), given input levels and the
  time; no pins, no `millis()`. Survives the wrap of `millis()` after 49.7 days (unsigned
  differences only).
- `interlock_device.hpp`: the channel map of the old box on top of it, and the spare relays.
- `InterlockOpta.ino`: pins (names from `variants/OPTA/pins_arduino.h` of the core 4.6.0: `I1`,
  `I2`, `RELAY1`..`RELAY4`, `LED_RELAY1`..`LED_RELAY4`, `LEDG`, `LEDR`), `Serial` (the two
  transport functions, the only place to change for Ethernet later), the watchdog
  (`mbed::Watchdog`, `cores/arduino/mbed/drivers/include/drivers/Watchdog.h`) and the lamps. No
  dynamic memory of its own, no waiting in `loop()`.
- `tests/`: `make` runs the tests on a PC (below).

Compile without the IDE (Docker): `AVR/tools/compile.sh AVR/devices/InterlockOpta arduino:mbed_opta:opta`
(see `AVR/tools/README.md`).

## Verified here / not verified

| Verified here (PC and container) | Not verified |
| --- | --- |
| Compiles for the Opta (core 4.6.0, arduino-cli 1.5.1) with `-Wall -Wextra`, no warning: 143072 bytes of flash, 59568 bytes of RAM | anything on an Opta: no board was available |
| The door logic: power-on, hold time, each door alone, an opening of 1 ms, bouncing, the wrap of `millis()`, an opening at the end of the hold (`make`, part a) | that `digitalRead(I1)`, `digitalRead(I2)` read terminals I1, I2 (the user manual says so; the core's two pin tables name different processor pins for A1) |
| The channels through libcom1: identity, order of `A`, sets of s1, s2 with read-back, set of i1 ignored, and that no line switches relays 1 and 2 (part b) | that `HIGH` on `RELAY1`..`RELAY4` closes the contact (the user manual's relay example says so) |
| The simulator's entry `interlockbox` gives the same replies as the firmware (part c) | how long `loop()` takes; an opening shorter than one pass of `loop()` is not seen |
| The linked firmware contains the float formatting (`_dtoa_r`, `_svfprintf_r`), so `%g` writes numbers | what the relays do while the bootloader runs, and whether the watchdog survives into it |
| Opening the port does not restart the Opta (the core resets only on 1200 baud: `USBSerial.cpp`), and with the port closed `Serial` writes return at once (`PluggableUSBSerial.h`) | that a write blocks only briefly while the port is open (the core's `USBCDC::send()` waits for the host to take the data) |
| | the watchdog's maximum time on this board (`get_max_timeout()`; its implementation is not in the core's sources) |
| | which way the door switches work, and what the supplies' interlock inputs carry |

## Open questions

- Do the door switches close when the door closes (A48)? Are they and their cable still there?
- Must the interlock contact latch (stay open after a door was opened until someone resets it),
  or is the latch of the IOC enough? Nothing is built for a latch.
- What do relays 1 and 2 go to, and with how much voltage and current? Below 300 mW (12.5 mA
  at 24 V, 60 mA at 5 V) the Opta's relays are not reliable (datasheet 5.9).
