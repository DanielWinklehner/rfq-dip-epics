# rfq-dip-epics
Repository for the development of an EPICS based control system for RFQ-DIP/MIST-1

### Folder Structure
- AVR: Files related to AVR microcontrollers (such as Arduinos)
    - communication_library
      - Original communication library designed to work with previous control system
      - Protocol: libcom1 over serial
    - lib/libstatcio (Deprecated)
      - A rewrite of the Arduino GPIO library for avr-libc that utilizes significantly more compile-time constants
      - Will eventually include USART + SPI bus handling for Serial and Ethercat
    - lib/libcom1
      - A libcom1 implementation w/o multiply queries
	- lib/libutil
	  - Collection of utilities used by libcom
- EPICS: Files related to EPICS (such as configuration files)
- RAS: RAS configuration
