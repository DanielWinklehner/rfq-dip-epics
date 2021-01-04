# libcom1

An adaptation of Aashish Tripathee's `communication_library` that is platform agnostic.
This communication library is for serial communication with Arduinos, and the library must be included in the Arduino libraries for access.

**REQUIRES LIBUTIL**

## Changes from `communication_library`
- Keywords:
    - "A" is used to query all channel
    - keywords "c", "i", and "n" are no longer used
    - Querying channels can only be done in one of two modes: single or all.

- Implementation detail changes:
    - IOHandler to handle IO events
    - Use of compile-time checks and optimizations to fail before compiling and to reduce binary size
    - User can set desired output buffer size

- Comparison using `ArduinoExample.ino` on an Atmega2560:
    - Flash Memory: 6804 vs 13382 bytes
    - RAM: 500 vs 622 bytes
    - Theoretical max polling rate for all channels: 822 Hz vs 151 Hz
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

## Platform Agnostic
- IOHandler object used to manage inputting and outputting from somewhere. With this, the user can define where to read a write from.
    - On devices that do not have serial, this could be a dummy buffer, or stdin/stdout on a terminal window, or even a file.
- This library should work with any C++11 or greater compatible compiler, and only uses the C standard library. The C++ compiler provides compile-time features to check for things, and to optimize away during compile-time. libutil provides the required C++ headers and utilities, so that they are not required.
- The Arduino IDE is not required, and projects can link this library as a header-only one.
