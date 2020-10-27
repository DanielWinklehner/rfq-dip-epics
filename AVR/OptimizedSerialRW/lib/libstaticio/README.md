This library handles IO, low-level communication, and the millis timer on AVRs

Currently Handles:
- GPIO (Digital and Analog)

TODO:
- USART (currently supporting 1 channel)
- SPI
- System Clock (millis, micros)
- TWI?

Digital GPIO:
- Functions provide dynamic access to pins.
- Direct port access should be used whenever possible. Lookup tables are used
to map pin numbers to their respective counterparts.

Analog GPIO:
- Dynamic access to PWM and Analog pins.
- Timer setup for PWM pins.
