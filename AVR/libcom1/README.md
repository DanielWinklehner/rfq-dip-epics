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

# Documentation
- To query one channel, send "q01", followed by the channel identification, the channel number, and the precision.
    - The output format is `o[vwxyz]` where:
        - v is the channel name (identification followed by number),
        - w is the sign (plus or minus) of the mantissa of scientific notation of the channel's value,
        - x is the absolute value of the mantissa of scientific notation, without the decimal and with the indicated precision as the length of x minus 1, of the channel's value (rounded up or down),
        - y is the absolute value of the exponent of scientific notation of the channel's value,
        - z is the sign (plus or minus) of the exponent of scientific notation of the channel's value.
    - For example, to query a channel with identification "a", number 1, and precision 3, send "q01a13", and if the channel's value is 4091.71, it should output `oa1+40923+`.
    - Limitations:
        - Channel identification must be one character, and channel number must each be one digit.
        - Channels cannot have the identification of 0x00 nor can it have a number of 0x00
        - Channel identifiers must be unique
        - Precision must be an integer between 0 and 6, inclusive, because floats lose precision over 6 decimal places.
        - The exponent output is at most 1 digit long. If it is longer, it is lost.
- To set a channel to a new value, send "s", followed by the channel identification, the channel number, and the set float value formatted as a string.
    - For example, to set a channel with identification "a" and number 1 to a value of 3.10, send "sa13.10".
    - This does not return any feedback.
- To query all channels, send "A".
    - The output format is, by default, `o%g:` (in printf format), with each `%g:` repeating for each channel in the order they are presented in the channel map, with the exception of the last channel, which will have its colon removed.
    - In the event where the format `%g` is not available, we use the %e format, with trailing zeros removed from the fractional part.

- Error messages:
    - ERR0 indicates that the queried input is unknown. The first letter of the input should be "q", "s", or "A".
    - ERR1 indicates that the queried precision is too large. The precision should be an integer between 0 and 6, inclusive.
    - ERR4 indicates that the queried channel could not be found.

- Other errors:
    - If the program stops running/responding, an assert has failed.
    - Compile-time errors should be readable enough to make out what is wrong

- printf support must be enabled when using debug mode (which can be enabled by editing the `libcom1_com.hpp` file)
