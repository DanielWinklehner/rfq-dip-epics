// InterlockOpta - the HV cage door interlock on an Arduino Opta RS485 (AFX00001), in place of
// the lost interlock box (AVR/devices/InterlockBox). NOT personnel protection: see README.md.
//
// Board: "Opta" of the package "Arduino Mbed OS Opta Boards" (fqbn arduino:mbed_opta:opta),
// main core (M7). Libraries: AVR/libcom1 and AVR/libutil of this repository.
//
// This file holds only what touches the board: pins, Serial, the watchdog and the lamps.
// What the box decides is in door_logic.hpp, the channels in interlock_device.hpp; both are
// tested on a PC (tests/). Pin names: variants/OPTA/pins_arduino.h of the core 4.6.0.
//
//   input I1  door 1 (channel i1)        relay 1, relay 2  interlock contacts: on only while
//   input I2  door 2 (channel i2)                          both doors are reported closed
//                                        relay 3, relay 4  spare relays s1, s2 (by command)
//   STATUS 1..4 lamps follow relays 1..4; the green lamp of the RESET button is on while both
//   doors are reported closed, its red lamp while a door is reported open.
//
// Status: compiled only. It has NOT been run on an Opta.

#include <mbed.h>          // mbed::Watchdog (cores/arduino/mbed/drivers/include/drivers/Watchdog.h)
#include <libcom1.hpp>
#include "interlock_device.hpp"

using namespace interlock_opta;

// ---- Constants ----------------------------------------------------------------------------------

// D8: hardware watchdog time in ms, 0 = no watchdog. Started in setup(), served in loop().
// Limited to the maximum the core reports (Watchdog::get_max_timeout()).
// Once started it cannot be stopped, and a software reset may not stop it either
// (hal/watchdog_api.h). See README.md, "Flashing", for what that means for an upload.
const uint32_t WATCHDOG_MS = 8000;

const uint8_t DOOR_PINS[2] = { I1, I2 };
const uint8_t RELAY_PINS[RELAYS] = { RELAY1, RELAY2, RELAY3, RELAY4 };
const uint8_t RELAY_LAMPS[RELAYS] = { LED_RELAY1, LED_RELAY2, LED_RELAY3, LED_RELAY4 };
const uint8_t LAMP_DOORS_CLOSED = LEDG;   // green lamp of the RESET button
const uint8_t LAMP_DOOR_OPEN = LEDR;      // red lamp of the RESET button

// ---- Transport: USB serial (D1). Ethernet later changes these two functions only. ---------------

mist1::com1::LineBuffer<IN_BUFFER> rx;

char* transport_read()          // one complete line, or "" when there is none yet; never waits
{
  while (Serial.available() > 0) {
    if (rx.feed((char)Serial.read()))
      return rx.take();
  }
  return rx.none();
}

void transport_write(char* line)
{
  Serial.println(line);
}

mist1::com1::IOHandler<OUT_BUFFER> io(&transport_read, &transport_write);
mist1::com1::SerialDevice<OUT_BUFFER, CHANNELS> device(io, channels);

// ---- Outputs ------------------------------------------------------------------------------------

void write_outputs()
{
  for (uint8_t r = 0; r < RELAYS; ++r) {
    PinStatus on = relay_on(r) ? HIGH : LOW;
    digitalWrite(RELAY_PINS[r], on);
    digitalWrite(RELAY_LAMPS[r], on);
  }
  digitalWrite(LAMP_DOORS_CLOSED, both_doors_closed() ? HIGH : LOW);
  digitalWrite(LAMP_DOOR_OPEN, both_doors_closed() ? LOW : HIGH);
}

void read_inputs(uint32_t now)
{
  update_inputs(digitalRead(DOOR_PINS[0]) == HIGH, digitalRead(DOOR_PINS[1]) == HIGH, now);
}

// ---- Arduino ------------------------------------------------------------------------------------

void setup()
{
  // Relays and lamps off first. digitalWrite() on a pin without a mode makes it an output with
  // that level in one step (cores/arduino/wiring_digital.cpp).
  for (uint8_t r = 0; r < RELAYS; ++r) {
    digitalWrite(RELAY_PINS[r], LOW);
    digitalWrite(RELAY_LAMPS[r], LOW);
  }
  digitalWrite(LAMP_DOORS_CLOSED, LOW);
  digitalWrite(LAMP_DOOR_OPEN, HIGH);

  for (uint8_t d = 0; d < 2; ++d)
    pinMode(DOOR_PINS[d], INPUT);

  if (WATCHDOG_MS != 0) {
    mbed::Watchdog& watchdog = mbed::Watchdog::get_instance();
    uint32_t max_ms = watchdog.get_max_timeout();
    watchdog.start(WATCHDOG_MS < max_ms ? WATCHDOG_MS : max_ms);
  }

  Serial.begin(115200);     // USB CDC: the baud rate is not used, see README.md
  device.set_identity(IDENTITY, __DATE__);
  // D9: no communication timeout. The interlock does not depend on the IOC.
}

void loop()
{
  uint32_t now = millis();
  read_inputs(now);
  write_outputs();          // an opened door switches the relays off before anything else
  device.service(now);      // at most one command, never waits for input
  write_outputs();          // a set of s1 or s2
  if (WATCHDOG_MS != 0)
    mbed::Watchdog::get_instance().kick();
}
