# rfq-dip-epics
Repository for the development of an EPICS based control system for RFQ-DIP/MIST-1

## Arduino

Here goes all the information about the Arduinos and serial communication

### communication_library

Written by Aashish Tripathee. A simple communications protocoll between serial port and Arduino. The library has to be copied into the Arduino library folder, or a symbolic link has to be created from the library folder to the location of the communication_library folder.

Sending "i\n\r" will send back a list of channel names.

Channels should be one letter and one number.

Querying (a) channel(s) is done by sending a string that is composed of these parts:

q<number of channels><channel 1 name><channel 1 significant digits>...<channel n name><channel n significant digits>\n\r
  
Example: q2c15c23\n\r queries the 2 channels "c1" and "c2" with 5 and 3 significant digits respectively.
