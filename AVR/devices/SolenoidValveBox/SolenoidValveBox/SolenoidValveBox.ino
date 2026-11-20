//#include <Channel.h>
//#include <Communication.h>
#include <libcom1.hpp>

// Set up serial communication
//char inputMessage[128];
//mist1::Communication com = mist1::Communication("Solenoid Valve Switchboard");

volatile int com_flag = 0;

// Solenoid Valve Variables (Relays). x8.
const int solenoidValvePins[] = {22, 24, 26, 28, 30, 32, 34, 36}; //
bool solenoidValveValues[] = {HIGH, HIGH, HIGH, HIGH, HIGH, HIGH, HIGH, HIGH}; // Relays are closed when pulled to ground. Default should be open (HIGH).

// Define pins for error state LED, communication LED
#define LED_ERR 12
#define LED_COM 13

// One pair of callbacks for all valves. `valve` is the index into solenoidValvePins,
// handed over by the channel map below (see mist1::com1::IndexedChannel).
void set_solenoid(uint8_t valve, float set_value){
  if (set_value == 1.0) {
    solenoidValveValues[valve] = LOW;
    digitalWrite(solenoidValvePins[valve], LOW);
  } else {
    solenoidValveValues[valve] = HIGH;
    digitalWrite(solenoidValvePins[valve], HIGH);
  }
}

float get_solenoid(uint8_t valve){
  if (digitalRead(solenoidValvePins[valve]) == LOW) {
    return 1.0;
  } else {
    return 0.0;
  }
}

using mist1::com1::IndexedChannel;
MakeChannelMap(lookup, 8, ({
    IndexedChannel('s', 1, &get_solenoid, &set_solenoid, 0),
    IndexedChannel('s', 2, &get_solenoid, &set_solenoid, 1),
    IndexedChannel('s', 3, &get_solenoid, &set_solenoid, 2),
    IndexedChannel('s', 4, &get_solenoid, &set_solenoid, 3),
    IndexedChannel('s', 5, &get_solenoid, &set_solenoid, 4),
    IndexedChannel('s', 6, &get_solenoid, &set_solenoid, 5),
    IndexedChannel('s', 7, &get_solenoid, &set_solenoid, 6),
    IndexedChannel('s', 8, &get_solenoid, &set_solenoid, 7),
  })
);

// Collects the received characters into complete lines. Never blocks, always NUL-terminates.
mist1::com1::LineBuffer<128> serial_in_buffer;
// Template parameter is buffer size for the output buffer
// (at least 14 bytes per channel plus 2, see mist1::com1::min_out_buffer_size)
mist1::com1::IOHandler<160> io_ctx(
    // Read from the serial port: one complete line, or an empty string if there is none yet
    []() -> char* {
      while (Serial.available() > 0) {
        if (serial_in_buffer.feed((char)Serial.read()))
          return serial_in_buffer.take();
      }
      return serial_in_buffer.none();
    },
    // Write to the serial port
    [](char* str){
      Serial.println(str);
    }
);

mist1::com1::SerialDevice<160, 8> device(io_ctx, lookup);

void setup()   { 
  // Init Com and Error LED's
  pinMode(LED_ERR, OUTPUT);
  pinMode(LED_COM, OUTPUT);
  digitalWrite(LED_COM, LOW);
  digitalWrite(LED_ERR, LOW);
  
  // Initialise the Arduino data pins.

  // Solenoid Valves.
  for (unsigned i = 0; i < sizeof(solenoidValvePins) / sizeof(int); i++) {
    pinMode(solenoidValvePins[i], OUTPUT);
    digitalWrite(solenoidValvePins[i], HIGH);
  }
      
  Serial.begin(115200);
  // Reported by the identity query "I", so the IOC can check what is on this port
  device.set_identity("SolenoidValveBox", __DATE__);
  /*
  com.add_channel(mist1::Channel("SOLENOID1", 's', 1, &set_solenoid1, &get_solenoid1));
  com.add_channel(mist1::Channel("SOLENOID2", 's', 2, &set_solenoid2, &get_solenoid2));
  com.add_channel(mist1::Channel("SOLENOID3", 's', 3, &set_solenoid3, &get_solenoid3));
  com.add_channel(mist1::Channel("SOLENOID4", 's', 4, &set_solenoid4, &get_solenoid4));
  com.add_channel(mist1::Channel("SOLENOID5", 's', 5, &set_solenoid5, &get_solenoid5));
  com.add_channel(mist1::Channel("SOLENOID6", 's', 6, &set_solenoid6, &get_solenoid6));
  com.add_channel(mist1::Channel("SOLENOID7", 's', 7, &set_solenoid7, &get_solenoid7));
  com.add_channel(mist1::Channel("SOLENOID8", 's', 8, &set_solenoid8, &get_solenoid8));
  */
}

void loop() {  

  // GUI Communication.
  digitalWrite(LED_COM, LOW);

  if (Serial.available()) {
    digitalWrite(LED_COM, HIGH);
  }

  // Handles at most one complete command per pass and never waits for more input.
  // service() also runs the optional streaming ("P<ms>") and communication timeout.
  device.service(millis());
}
