# communication_library

Written by Aashish Tripathee. A simple communications protocol between serial port and Arduino.

### Installation
The library has to be copied into the Arduino library folder, or a symbolic link has to be created from the library folder to the location of the communication_library folder.

### Protocol:
Channels should be one letter and one number.

* Info: `i\n\r` 
  * Returns a list of channel names
* Query: `q<a>[<b><c>]`
  * `a` (2 bytes): Number of channels to query
  * `b` (2 bytes): Channel Name, letter followed by number
  * `c` (1 byte): Decimal places of precision (in scientific notation). Must be less than 7
  * `[<b><c>]` is repeated `a` times
  * Ex: `q02c15c23`: Query 2 channels: c1 with 5 places of precision, and c2 with 3 places of precision
* Query Response: `o[<b>±<d><e>±]`
  * `d` (value of `c` + 1 bytes): Coefficient of exponential with c decimal places of precision (but remove the decimal point). First ± denotes sign of coefficient.
  * `e` (1 byte): Exponent of exponential. Second ± denotes sign of exponent.
  * `[<b>±<d><e>±]` is repeated `a` times.
  * Ex: `ol1-66673+s3+88811-`: Channel l1 has value -6.667e+03 and channel s3 has value +8.881e-01
* Setting: `s<b><f>`
  * `f` (At most 124 bytes): String repr of float. Represents the value to be set.
  * Ex: Ex: sl12.34
