# The dipole supplies through the NI box: mist2daq

Task T24 (work package WP11, phase 2). The dipole magnet supplies are old and have an analog
interface only ("analog 0-10 V", plan); an NI USB-6001 at the lab computer drives them, today from
LabVIEW. This note describes what replaces LabVIEW's side of the box: a small Python service,
`daq/mist2daq`, that owns the box and serves it to an IOC, and the records `EPICS/Db/dipole.db`.
Installation on the lab computer: [../../daq/README.md](../../daq/README.md).

Status: built and tested in the emulation with the `sim` backend. The `nidaqmx` backend is written
from NI's documentation and has never run against a box. Whether NI's driver for Linux serves the
USB-6001 at all is open (section 6). The devices stay "later" in the plan and no IOC of the
emulation loads `dipole.db` yet.

## 1. Design

```
   operator / scan program ── CA ──> IOC: dipole.db + libcom1_device.db + first_contact.db
                                         │  libcom1.proto, unmodified (asyn IP port)
                                         │  TCP, libcom1 protocol 2 (A, S, I ... as for an Opta)
                                     mist2daq (lab computer) ── status port, read-only JSON
                                         │  backend: nidaqmx (NOT VERIFIED) | sim (tests)
                                     NI USB-6001 ── AO 0-10 V ──> supply program input
                                                 <── AI ──────── supply current monitor
```

Why a libcom1 device over TCP and not a Python soft IOC (the plan's first idea, "Python soft IOC
(nidaqmx)"): the IOC then needs nothing new. Records, protocol file, identity records, alarm
behaviour and the first-contact rule are those of the Arduino boards and the Optas, already tested
(`emulation/devtest/libcom1_devices`, `faradaycup`). A soft IOC would be a second kind of server
with its own Channel Access, its own alarm handling and its own tests. The service stays small:
volts in, volts out, a line protocol. Its protocol is proven line by line against the real
library (section 7).

Parts (`daq/mist2daq/`):

| Module | Does |
|---|---|
| `protocol.py` | libcom1 protocol 2, device side: commands, errors, identity, streaming, communication timeout, line framing (`LineBuffer<128>`). No I/O, no clock. One addition: a setter may refuse a set (section 4) |
| `config.py` | the configuration file, checked completely before anything is opened; unknown keys are errors |
| `backends.py` | `sim` and `nidaqmx` behind one interface: `open()`, `write(physical, volts)`, `read_inputs()`, `close()` |
| `service.py` | `Daq`: channels, scaling, limits, held set values, the timeout action. `Server`: TCP, one client at a time, the status port |

The channels are one libcom1 device: an output channel (`o1`) is read/write, and reading it gives
the set value the service holds (in the unit); an input channel (`i1`) is read-only and gives the
measured value in the unit. The IOC polls `A` every 0.5 s and gets `o<held>:<read-back>`.

## 2. A set and a read, step by step

A set (`caput dipole:current:set 25`):
1. The ao record clamps to DRVL/DRVH (aoRecord.c, convert) and StreamDevice sends
   `So125.000000` (`com1_setLink_flt_ack`, `%f`).
2. The service reads the number as the library does (strtod, then a 32-bit float; anything else
   on the line: `ERR5`), finds the channel (`ERR4`), checks that it is writable (`ERR7`).
3. It checks the value against the channel's `limits` (in A) and the resulting voltage against
   `volts`. Outside: `ERR5`, nothing written, the held value unchanged.
4. volts = (value - offset) / per_volt; the backend writes it. If the write fails: `ERR7`, and
   the held value becomes "not known" (nan), because what the output does now is not known.
5. Success: the held value is the set value, the reply is `ok`, the record is NO_ALARM. A reply
   other than `ok` puts the set record into INVALID (EPICS/README, Acknowledged sets).

A read (every 0.5 s, `dipole:data`, `read_all_array`):
1. The IOC sends `A`. The service reads one sample of every input from the backend.
2. For each channel in order: an output gives its held value (`nan` before the first set), an
   input gives offset + per_volt × volts (`nan` when the read failed).
3. The reply `o<v1>:<v2>` is parsed with `%g` (StreamDevice uses strtod, which also reads `nan`).
4. `:current:held` and `:current:get` follow the array by CP links with MS. A `nan` element makes
   the ai INVALID/UDF (aiRecord.c: `udf = isnan(val)`); a silent service makes `:data` INVALID
   and with it both element records.

## 3. Start, stop, lost client: what the service does by itself

Nothing. In detail:

| Event | Outputs | What the IOC sees |
|---|---|---|
| Start | **Nothing written.** The `nidaqmx` backend creates the task of an analog output only at the first set of that output. Every held value is "not known" (nan) | `:current:held` INVALID/UDF; `:current:set` INVALID/UDF after an IOC start too (first contact waits for a valid held value) |
| A client disconnects | Nothing written; a stream it asked for is switched off | – |
| No valid command for `comm_timeout_s` (5 s) | `on_comm_lost: hold` (default): nothing written, one log line. `ramp_to_zero` (a setting, off): each output with a known value other than 0 ramps to 0 in its unit at `ramp_rate` per second, in steps of `ramp_period_s`; an output never set is left alone; a set from a client ends the ramp of that output; the ramp continues when the client comes back without setting | – |
| Stop (SIGTERM, `systemctl stop`) | Nothing written; the backend clears its tasks. What the NI box's output does after its task is cleared: **not known** (not found in NI's documentation; to be measured, daq/README.md) | every read record INVALID within 15 s (measured 5.5 s), see section 7 |
| Start after a stop | as Start: the held value is "not known" again, although the output of the box may still be at the last value | read records valid again within 30 s (asyn retries a lost connection every 20 s, asynManager.c `DEFAULT_SECONDS_BETWEEN_PORT_CONNECT`; measured 19.9 s); `:current:held` INVALID/UDF until the next set. `:current:set` keeps its last value and NO_ALARM: it is not processed by polls |
| Box unplugged or its driver failing | a set answers `ERR7` and its held value becomes nan; a read sends `nan` | the set record INVALID; the element records INVALID/UDF |
| A second client while one is connected | the newcomer is closed at once without a reply while the first client has sent a valid command within `takeover_s` (10 s); after that silence the newcomer replaces the first | nothing: the IOC's connection is not disturbed (measured, section 7) |

The second-client rule differs from the Opta example and the simulator, where a new connection
always replaces the old one. Here a stray client (a test script, a second IOC by mistake) would
otherwise throw the IOC off every time it connects. The IOC's own reconnection is not affected:
when an IOC process ends, its socket is closed and the place is free at once (measured with the
IOC restart in the device case); a connection left half-open by a crashed IOC computer is replaced
after `takeover_s`.

Wrong input:

| Input | Reply | Applied |
|---|---|---|
| unknown command, line longer than 127 characters | `ERR0` | no |
| `g`/`S`/`s` to a channel that does not exist | `ERR4` | no |
| set to an input channel, get of a write-only channel | `ERR7` | no |
| malformed value, `nan`, `inf`, beyond a 32-bit float | `ERR5` | no |
| value outside `limits` or `volts` (**service's addition**) | `ERR5` | no |
| write to the box failed (**service's addition**) | `ERR7` | not known: held value nan |
| a line without its line feed | nothing until the line feed arrives | – |

The two additions use existing error codes so that `libcom1.proto` and every client stay
unchanged. `ERR5` reads "Malformed command or value" in the README, `ERR7` "not writable". The
README does not mention these two meanings; a line there would make them official (not done: the
README is not part of this task).

## 4. Configuration (`daq/config/dipole.yaml`, every key)

`service:`

| Key | Default | Meaning |
|---|---|---|
| `identity` | `mist2daq` | `ID=` of the identity reply (`:id` record); no `;` |
| `listen_host`, `listen_port` | `127.0.0.1`, 5100 | where the IOC connects. The protocol has no authentication |
| `status_host`, `status_port` | `127.0.0.1`, none | read-only status port: `{"cmd": "status"}` gives held values, volts written, input volts, counters (commands by first letter, sets applied, refused, failed, timeouts), the client, refused and replaced clients; any other request is answered with an error |
| `takeover_s` | 10 | silence of the connected client after which a new client replaces it |
| `comm_timeout_s` | 5 | libcom1 communication timeout (a valid command is a sign of life); 0 = off |
| `on_comm_lost` | `hold` | `hold` or `ramp_to_zero` (the owner decides) |
| `ramp_period_s` | 0.1 | step period of a ramp to zero |

`backend:` `type` (`sim` or `nidaqmx`); for `nidaqmx`: `device` (the name NI-DAQmx gives the box,
checked at the start) and `product_type` (the service refuses to start on another product); for
`sim`: `sim.initial_volts` (`{physical: volts}`, default 0 V for every output, the USB-6001's
power-on state) and `sim.inputs` (`{physical: {follow: <output>, gain, tau_s, offset_v}}` or
`{volts: <fixed>}`).

`channels:` a list in query-all order.

| Key | Out | In | Meaning |
|---|---|---|---|
| `id` | yes | yes | libcom1 channel: one letter and one digit (`o1`, `i1`), unique |
| `name` | yes | yes | a name for logs and the status port |
| `direction` | `out` | `in` | |
| `physical` | yes | yes | NI-DAQmx physical channel, e.g. `Dev1/ao0`, `Dev1/ai0` |
| `unit` | yes | yes | engineering unit, e.g. `A` |
| `per_volt` | yes | yes | unit per volt, not 0; negative for a reversed polarity |
| `offset` | yes | yes | value at 0 V (default 0) |
| `limits` | yes | – | [low, high] in the unit: a set outside is refused (`ERR5`) |
| `volts` | yes | yes | out: [low, high] in V, a set whose voltage is outside is refused; also the range given to NI-DAQmx. in: the measurement range given to NI-DAQmx |
| `terminal` | – | yes | `DEFAULT`, `RSE`, `NRSE`, `DIFF` (NI-DAQmx terminal configuration) |
| `ramp_rate` | yes | – | unit per second, needed only for `on_comm_lost: ramp_to_zero`; 0 must then lie within `limits` and `volts` |

Value = offset + per_volt × volts in both directions; a set's voltage = (value − offset) /
per_volt. Limits are compared as 32-bit floats (a set of exactly the limit passes). The service
refuses to start when `limits` and `volts` have no value in common.

## 5. Records (`EPICS/Db/dipole.db`)

| PV | Type | Meaning |
|---|---|---|
| `$(DEVICE):data` | aai | `read_all_array`, every 0.5 s (`SCAN` macro) |
| `$(DEVICE):current:set` | ao | acknowledged set (`com1_setLink_flt_ack`), DRVL/DRVH required macros |
| `$(DEVICE):current:held` | ai | the set value the service holds; INVALID/UDF when "not known" |
| `$(DEVICE):current:get` | ai | the supply's current monitor |
| `$(DEVICE):id`, `:firmware`, `:channels` | | `libcom1_device.db`: `DipoleDAQ`, `mist2daq-0.1`, `o1,i1` |

First contact: `first_contact.db` with `REQ=$(DEVICE):current:set`, `RB=$(DEVICE):current:held`
fits an analog value unchanged: its check needs RB valid (a nan is INVALID, so no take-over while
the service holds nothing) and REQ never processed (UDF); the copy goes through the ao in
simulation mode, so nothing is sent. One limit: the copy passes the ao's drive limits, so a held
value outside DRVL/DRVH would be shown clamped; therefore DRVL/DRVH should equal the service's
limits or lie within them.

The element records use CP links, not a forward link from the array as `faradaycup.db` and
`solenoidbox.db` do: in the device case the forward-linked record showed the previous poll's value
(the read-back 0.5 s late against the lag model). Measured, not traced in the source; the same
probably holds for those databases (not checked, not changed: not part of this task).

## 6. NI on Linux

What NI's documentation says, as far as it could be read on 2026-11-24:

- **The USB-6001 is not listed for NI-DAQmx on Linux.** The NI-DAQmx for Linux readme version
  21.3 lists its supported devices by family (CompactDAQ, X Series, M Series, S Series, SC
  Express, AO Series, Digital I/O, TIO, DSA); the USB column of the X and M Series tables is empty
  and no USB-600x device appears (https://www.ni.com/pdf/manuals/378678b.html, "Supported
  Devices"). Later readmes (2023 Q1, https://ni.com/pdf/manuals/ni-daqmx-linux-2023-q1.html; 2023
  Q3, https://ni.com/pdf/manuals/ni-daqmx-linux-2023-q3.html) no longer list devices and refer to
  NI's "Hardware and Operating System Compatibility" page; that page builds its table in the
  browser (https://www.ni.com/en/support/documentation/compatibility/21/ni-hardware-and-operating-system-compatibility.html)
  and its content could not be read here. **Not settled from an NI page.**
- An NI knowledge-base article "USB DAQ Devices Support For Linux"
  (https://knowledge.ni.com/KnowledgeArticleDetails?id=kA00Z0000019NhFSAU) appears in search
  results with the statement that USB multifunction DAQ devices are not supported on Linux; the
  page could not be fetched (certificate error), so its text is NOT CONFIRMED. NI forum threads
  (not NI documentation) say the same for the USB-6001 (e.g. "Is NI-DAQ USB 6001 compatible with
  ubuntu?", forums.ni.com, 2022; fetching was refused).
- Ubuntu versions of NI's Linux driver bundle: NI Linux Device Drivers 2026 Q3 names Ubuntu LTS
  22.04 and 24.04 (beside RHEL 9.6/10.0, openSUSE Leap 15.6/16.0); the per-driver cells could not
  be read (https://www.ni.com/en/support/documentation/compatibility/26/ni-linux-device-drivers-2026-q3-compatibility.html).
  NI-DAQmx 2023 Q3: Ubuntu 20.04 and 22.04; 2023 Q1 and 21.3: Ubuntu 18.04 and 20.04 (the readmes above).
- NI's Python package `nidaqmx` 1.7.0 (PyPI, the docstrings are its documentation): "supports
  Windows and Linux operating systems where the NI-DAQmx driver is supported", CPython 3.9 or
  later, `python -m nidaqmx installdriver` (https://nidaqmx-python.readthedocs.io/en/stable/).
- USB-6001 specifications (NI, 374369A-0112, June 2014, Japanese edition; the English PDF on
  ni.com could not be fetched): AO 2 channels, 14 bit, ±10 V, 5 kS/s per channel, ±5 mA drive,
  output impedance 0.2 Ω, **power-on state 0 V, power-on glitch −7 V for 10 µs** (p. 2); AI 8
  single-ended or 4 differential, 14 bit, ±10 V only, 20 kS/s aggregate (p. 1).
  (https://download.ni.com/support/manuals/374369a_0112.pdf)

Consequence: until the owner answers the plan's question "Does the LabVIEW dipole scan run on
this computer under Ubuntu today, with NI's driver for the USB-6001 installed?", the `nidaqmx`
backend may have nothing to talk to. If LabVIEW drives the box under Ubuntu today, NI-DAQmx serves
it there and the question is settled by trying (`--check`). If not, what else could serve or
replace the box (none of it built):

- a Windows computer with NI-DAQmx (the lab computer was Windows until now); mist2daq runs there
  unchanged, the IOC connects over TCP (the service needs Python, PyYAML, nidaqmx only);
- NI hardware that NI-DAQmx supports on Linux, e.g. a CompactDAQ chassis with an analog output
  and an analog input module (forum statements name cDAQ-9171/9174/9178; check NI's page);
- a different analog interface with a Linux path already in this system: a microcontroller
  board with a 0-10 V analog output and input (hardware to be chosen, not checked) running
  libcom1: the IOC side would stay exactly as built here (same protocol, same records), only the
  service disappears;
- the protocol of the USB-6001 is not published by NI; no open driver for it is known here.

## 7. Tests

```
docker run --rm --network none --user $(id -u):$(id -g) -e HOME=/tmp -v "$PWD":/repo -w /repo \
    --entrypoint python3 mist2-tools:dev -m unittest discover -s daq/tests -t daq      # 47 tests
docker run --rm --network none --user $(id -u):$(id -g) -e HOME=/tmp -v "$PWD":/repo -w /repo \
    --entrypoint bash mist2-tools:dev daq/tools/compare_libcom1.sh   # real library, 122 lines, 0 differences
emulation/devtest/run.sh emulation/devtest/dipole                     # 12 tests, about 50 s
```

1. Unit tests (`daq/tests`, no EPICS): the protocol (every command and error of the README, NUL,
   long and broken lines, streaming, the communication timeout), scaling and offset in both
   directions with a negative `per_volt`, limits in A and in V, the `sim` backend's lag, "not
   known" before the first set and after a failed write, hold and ramp to zero, the
   configuration's checks, the TCP server (second client refused, replacing a silent one, the
   stream ending with its client, the read-only status port).
2. Against the libcom1 simulator (`test_against_simulator.py`): the conversation of
   `AVR/libcom1/tests/script.hpp` (63 steps) and 64 more lines, reply, frames, result code and
   timeout state per step, identical. Against the real library (`compare_libcom1.sh`, the way
   `emulation/sim/run_tests.sh` does it, format `g`): identical. Differences to the library that
   the comparison does not cover, by design: the two refusals of section 3, the stream switched
   off per client, the second-client rule.
3. The device case `emulation/devtest/dipole`: the service with the `sim` backend as the case's
   simulator (`sim.cmd` → `run_service.sh`, which also stops and starts it on request), one IOC
   with `dipole.db` twice (`dipole` with drive limits 0-80 A inside the service's 0-100 A,
   `wide` with -50-150 A for the refusal), `libcom1_device.db`, `first_contact.db`. The status
   port (6000) gives the output voltage and the commands received, not the IOC.

## 8. Unknowns (each is a configuration value, or stays out)

| Unknown | Where it goes | Value now |
|---|---|---|
| Does NI-DAQmx for Linux serve the USB-6001 on the lab computer? | section 6 | not known; NI's readable pages do not list it |
| Ubuntu version of the lab computer | – | not known (plan question) |
| How many supplies | one `o<n>`/`i<n>` pair and one `dipole.db` load each | ASSUMED one |
| Which NI channels | `physical` | ASSUMED `Dev1/ao0`, `Dev1/ai0` |
| NI-DAQmx device name | `backend.device` | ASSUMED `Dev1` |
| Amperes per volt, set and monitor | `per_volt` | ASSUMED 10 A/V both |
| Offset | `offset` | ASSUMED 0 |
| Current range | `limits`, DRVL/DRVH | ASSUMED 0-100 A |
| Voltage range of the program input | `volts` | 0-10 V (plan: "analog 0-10 V") |
| Polarity | sign of `per_volt` | ASSUMED positive |
| Monitor output exists, its range, wiring (single-ended or differential) | the `in` channel, `terminal` | ASSUMED present, RSE |
| Enable or other inputs of the supply | stays out (no channel) | not known |
| Slow changes needed | stays out: no rate limit in the service | not known |
| Action at lost communication | `on_comm_lost` | `hold` (owner decides) |
| Output after the task is cleared / USB unplugged | – | not known; measure (daq/README.md) |
| Which IOC serves the dipole, so where the service listens | `listen_host`, st.cmd | ASSUMED same computer, 127.0.0.1 |
| Whether the service's user needs a group or udev rule to open the box | – | not known |
