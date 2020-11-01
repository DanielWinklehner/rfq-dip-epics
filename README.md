# rfq-dip-epics
Repository for the development of an EPICS based control system for RFQ-DIP/MIST-1

### Folder Structure
- AVR: Files related to AVR microcontrollers (such as Arduinos)
    - communication_library
      - Original communication library designed to work with previous control system
      - Protocol: libcom1 over serial
    - SerialReadWrite
      - EPICS playground over the serial bus
    - OptimizedSerialRW
      - EPICS playground w/o the Arduino library
      - Protocol: EPICS and libcom1 over serial
    - lib/libstatcio
      - A rewrite of the Arduino GPIO library for avr-libc that utilizes significantly more compile-time constants
      - Will eventually include USART + SPI bus handling for Serial and Ethercat
    - lib/libcom
      - A libcom1 implementation w/o multiply queries using avr-libc
      - A libcom2 implementation using avr-libc
- EPICS: Files related to EPICS (such as configuration files)
