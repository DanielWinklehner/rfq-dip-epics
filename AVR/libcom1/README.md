# libcom1

An adaptation of Aashish Tripathee's `communication_library` that is platform agnostic.
This communication library lets a microcontroller expose named channels to a control system (EPICS via StreamDevice) over a line based text protocol. The library must be included in the Arduino libraries for access.

**REQUIRES LIBUTIL**

- Code usage: `#include <libcom1.hpp>` in source file, after importing the library
- Start from `examples/CommunicationExample` (serial) or `examples/EthernetExample` (TCP, Arduino Opta).

## Quick start

```cpp
#include <libcom1.hpp>

float get_temp()        { return read_my_sensor(); }
void  set_valve(float v){ digitalWrite(7, v == 1.0f); }

using mist1::com1::Channel;
MakeChannelMap(lookup, 2, ({
    Channel{ 't', 1, &get_temp, nullptr },    // read-only
    Channel{ 'v', 1, nullptr, &set_valve },   // write-only
  })
);

mist1::com1::LineBuffer<128> rx;              // complete lines, never blocks

mist1::com1::IOHandler<128> io(
    []() -> char* {                           // read: one line, or "" if none yet
      while (Serial.available() > 0) {
        if (rx.feed((char)Serial.read()))
          return rx.take();
      }
      return rx.none();
    },
    [](char* str) { Serial.println(str); }    // write
);

mist1::com1::SerialDevice<128, 2> device(io, lookup);

void setup() {
  Serial.begin(115200);
  device.set_identity("MyDevice", __DATE__);
}

void loop() {
  device.service(millis());                   // returns at once when there is nothing to do
}
```

## Commands

One command per line, terminated by LF (a CR before it is ignored). `<c><n>` is a channel: one identification character and one digit.

| Command | Meaning | Reply |
| --- | --- | --- |
| `A` | query all channels | `o<v1>:<v2>:...:<vN>` in the order of the channel map |
| `g<c><n>` | query one channel | `o<value>` |
| `s<c><n><value>` | set a channel | nothing on success |
| `S<c><n><value>` | set a channel, acknowledged | `ok` |
| `I` | identify | `oID=<name>;FW=<version>;PROTO=2;CH=<c1n1>,<c2n2>,...` |
| `P<ms>` | stream all channels every `<ms>` milliseconds, `0` = off | `ok`, then frames `t<seq>:<device ms>:<v1>:...:<vN>` |
| `q01<c><n><p>` | legacy single query with precision `<p>` (0 to 6) | `o<c><n><sign><digits><exponent digit><exponent sign>` |

`g`, `S`, `I` and `P` are new in protocol version 2. Version 1 firmware answers them with `ERR0`, so mixed installations fail loudly instead of silently.

- Values are written as `%g`. On Arduino AVR, which has no float `printf`, they are written as `%e` with the trailing zeros of the fraction removed (`+2.5e+01`). Both parse with `%g`.
- Not-a-number and infinities are sent as `nan`, `inf` and `-inf`.
- A channel without a getter keeps its position in the `A` reply and reads as `0`.
- Stream frames: `<seq>` counts frames and wraps at 65535, so a gap means lost frames. `<device ms>` is the time passed to `service()` when the frame was built, so the sampling instant does not depend on transport delays. A slow `loop()` skips frames, it does not send bursts.
- A frame is never sent in the middle of a reply, but one that is already on the wire when a command arrives reaches the client before the reply. A client that streams and also sends commands has to skip lines starting with `t` while it waits for a reply. A StreamDevice protocol cannot do that: it takes the frame for the reply and reports a mismatch although the command was executed (9 of 80 acknowledged sets at a 100 ms period in a test IOC). In an IOC, poll with `A` and leave streaming off on every port that has records waiting for a reply.
- Legacy query example: channel `a1`, precision 3, value 4091.71 gives `oa1+40923+`. The format has one exponent digit, so it only covers 1e-9 to 9.99e9. Outside that range the device answers `ERR6`. Use `g` instead, which has no such limit and needs no custom StreamDevice converter.

Limitations:
- Channel identification must be one character, and channel number must be one digit.
- Channels cannot have the identification of 0x00 nor can it have a number of 0x00.
- Channel identifiers must be unique (checked at compile time).
- A set value must be one finite number filling the rest of the line. Anything else is rejected and the setter is not called.

## Error replies

| Reply | Meaning |
| --- | --- |
| `ERR0` | Unknown command, or a line too long for the input buffer (it is discarded, never executed in part). |
| `ERR1` | Legacy query: precision too large, it must be 0 to 6. |
| `ERR2` | The reply does not fit the output buffer (identity too long, or the buffer is too small for streaming). |
| `ERR3` | Legacy query asking for anything other than one channel (`q01`). |
| `ERR4` | The channel does not exist. |
| `ERR5` | Malformed command or value (`Sa1`, `Sa1abc`, `Sa1nan`, `Pabc`). |
| `ERR6` | Legacy query: the value cannot be represented with one exponent digit, or is not finite. |
| `ERR7` | The channel is not readable (for `g`, `q`) or not writable (for `s`, `S`). |

## Using the library

### Channels
- `Channel{ 'a', 1, &getter, &setter }` with `float getter()` and `void setter(float)`.
- Pass `nullptr` for a missing getter or setter. Do not use dummy functions: a getter that returns nothing is undefined behaviour and puts garbage into the `A` reply.
- `IndexedChannel('s', 1, &get, &set, 0)` with `float get(uint8_t)` and `void set(uint8_t, float)`: the last argument is handed to the callbacks, typically an index into a pin table. Many similar channels then share one pair of functions, see `devices/SolenoidValveBox`.

### Buffers
- The output buffer (template parameter of `IOHandler` and first one of `SerialDevice`) must hold the `A` reply for the worst case values: 14 bytes per channel plus 2. `mist1::com1::min_out_buffer_size(N)` computes it and `SerialDevice` refuses to compile with less. For streaming add 17 bytes (`min_stream_buffer_size(N)`); without them `P<ms>` answers `ERR2`.
- `LineBuffer<N>` holds one received line of up to N - 1 characters.

### Reading input: use `LineBuffer`
Do not read with `Serial.readBytesUntil()`:
1. It does not NUL-terminate. A short command inherited the tail of the previous longer one: `sa1100` followed by `sa15` was parsed as 500.
2. It waits for the stream timeout (1 s by default) when a line never ends. One stray byte on the line stalled `loop()` for a second, including whatever else the sketch does there.

`LineBuffer` returns complete, terminated lines only and never waits.

### `service()`, `communicate()`, `intr_communicate()`
- `service(now_ms)` processes at most one received line and runs everything that depends on time (streaming, communication timeout). Call it on every pass of `loop()` with `millis()`.
- `communicate()` only processes a received line. Both return the `PRC_*` / `ERR_*` code of what happened.
- `intr_communicate()` is the old I/O Intr mode and is kept for compatibility: without input it sends all channels on every call, as fast as it is called. Streaming replaces it.

### Identity
`device.set_identity("InterlockBox", __DATE__)` sets what `I` reports. The control system can then check that the expected device, firmware and channel order are on a port. The `A` reply is positional, so a changed channel map otherwise shifts every PV without any error.

### Communication timeout
`device.set_comm_timeout(5000, &outputs_off)` calls `outputs_off()` once when no valid command arrived for 5 s, and again after communication came back and was lost again. `device.comm_lost()` tells the current state. Garbage (`ERR0`) does not count as a sign of life.
- It is off by default. Which state is safe, and whether dropping to it when an IOC restarts is acceptable, is a decision per device.
- A client that only listens to a stream never sends anything. Let it send `I` every few seconds as a heartbeat. An IOC that polls needs nothing extra, every poll counts.
- This is not a replacement for a hardware watchdog or for hard wired interlocks.

### Serial or TCP
The library does not touch `Serial`. The two functions given to `IOHandler` are the transport, so moving a device to Ethernet only changes those (see `examples/EthernetExample`). Over TCP, send the reply and its line feed in a single `write()`: two writes become two segments and the second one can be held back for tens of milliseconds.

On the EPICS side only the asyn port changes (`drvAsynIPPortConfigure` instead of `drvAsynSerialPortConfigure`). `EPICS/Db/libcom1.proto` is the same for both.

## Platform Agnostic
- IOHandler object used to manage inputting and outputting from somewhere. With this, the user can define where to read a write from.
    - On devices that do not have serial, this could be a dummy buffer, or stdin/stdout on a terminal window, or even a file.
- This library should work with any C++11 or greater compatible compiler, and only uses the C standard library. The C++ compiler provides compile-time features to check for things, and to optimize away during compile-time. libutil provides the required C++ headers and utilities, so that they are not required.
- The Arduino IDE is not required, and projects can link this library as a header-only one.
- Float formatting: `dtostre()` on Arduino AVR, `snprintf("%g")` everywhere else. Define `LIBCOM1_USE_DTOSTRE` to 0 or 1 to override the choice.
- printf support must be enabled when using debug mode (which can be enabled by editing the `libcom1_com.hpp` file).

## Tests

```
cd tests
make            # unit tests on a PC, four configurations, with address and UB sanitizers
make avr-sim    # the same conversation on a simulated ATmega2560 and on the PC, compared line by line
```

- `make` needs g++. It builds every test for both formatting code paths (`snprintf` and a `dtostre` stand-in) and for gnu++11 (what the Arduino AVR core uses) and C++17.
- `make avr-sim` needs `avr-g++`, `avr-libc` and `simavr` (Debian/Ubuntu: `apt install gcc-avr avr-libc simavr`). It runs the library with the real avr-libc `dtostre()` and `strtod()`, which the PC build can only imitate.
- Each bug fixed so far has a regression test in `tests/test_libcom1.cpp`.

## Changes from `communication_library`
- Keywords:
    - "A" is used to query all channel.
    - keywords "c", "i", and "n" are no longer used.
    - Querying channels can only be done in one of two modes: single or all.

- Implementation detail changes:
    - IOHandler to handle IO events.
    - Use of compile-time checks and optimizations to fail before compiling and to reduce binary size.
    - User can set desired output buffer size.

- Comparison using `ArduinoExample.ino` on an Atmega2560, measured with the first version of libcom1 (protocol 1). Protocol 2 adds about 3 kB of flash and 150 to 260 bytes of RAM per sketch (measured on the sketches in `devices/`).
    - Flash Memory: 6804 vs 13382 bytes
    - RAM: 500 vs 622 bytes
    - Theoretical max polling rate for all channels: 220 Hz vs 151 Hz
    - Processing time in microseconds:
      | Command | libcom1 (w/ printf) | communication_library |
      | --- | --- | --- |
      | q01s14 | 852 | 1816 |
      | q01s24 | 844 | 1824 |
      | q01s34 | 840 | 1816 |
      | q01s44 | 840 | 1836 |
      | q01l11 | 808 | 1592 |
      | A | 4530 | x |
      | q05s14s24s34s44l11 | x | 6608 |
      | sl11 | 488 | 708 |

- Other errors:
    - If the program stops running/responding, an assert has failed.
    - Compile-time errors should be readable enough to make out what is wrong.
