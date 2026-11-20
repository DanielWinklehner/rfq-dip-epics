//#include <Channel.h>
//#include <Communication.h>
#include <libcom1.hpp>

// A PS Controller for the HV Power Supplies
// * PS1 = Glassman, Einzel Lens, Lower Row of BNC's
// 0-10 V on Voltage control, 0-10 V on Current Control
// * PS2 = Farnell HiVolt, Ion Source HV, Upper Row of BNC's
// 0-10 V on Voltage Control, 0-10 V on Current Control

// Set up serial communication
//char inputMessage[128];
//mist1::Communication com = mist1::Communication("HVPSController");

// Define pins for power supply control voltages
#define TSY_V_OUT 35

// Define pins for power supply read voltages
#define TSY_V_IN 13

void set_tsy_v (float value){
  analogWrite(TSY_V_OUT, (int)(value / 3.3 * 255.));
}

float get_tsy_v (){
  analogRead(TSY_V_IN);
  delay(1);
  return analogRead(TSY_V_IN) / 1023. * 3.3;
}

using mist1::com1::Channel;
MakeChannelMap(lookup, 1, ({
    Channel{ 'v', 1, &get_tsy_v, &set_tsy_v},
  })
);

// Collects the received characters into complete lines. Never blocks, always NUL-terminates.
mist1::com1::LineBuffer<128> serial_in_buffer;
// Template parameter is buffer size for the output buffer
// (at least 14 bytes per channel plus 2, see mist1::com1::min_out_buffer_size)
mist1::com1::IOHandler<128> io_ctx(
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

mist1::com1::SerialDevice<128, 1> device(io_ctx, lookup);

void setup() {
  Serial.begin(115200);
  // Reported by the identity query "I", so the IOC can check what is on this port
  device.set_identity("Teensy_PID", __DATE__);

  // Init V and I output PWM's
  pinMode(TSY_V_OUT, OUTPUT);

  // Set them to 0 V
  analogWrite(TSY_V_OUT, 0);;
  
  //com.add_channel(mist1::Channel("HV_GLAS_V", 'v', 1, &set_tsy_v, &get_tsy_v));
 
}

void loop() {
  
  // GUI Communication.

  // Handles at most one complete command per pass and never waits for more input.
  // service() also runs the optional streaming ("P<ms>") and communication timeout.
  device.service(millis());
}

