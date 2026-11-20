//#include <Channel.h>
//#include <Communication.h>
#include <libcom1.hpp>

// Set up serial communication
//char inputMessage[128];
//mist1::Communication com = mist1::Communication("Ammeter");

#define BNC1 2
#define BNC2 3

long value_1 = 0;
long value_2 = 0;

float curr_1 = 0.0; 
float curr_2 = 0.0;

int samples = 100;
int resolution = 16;
float scaling = 100.0 / (pow(2.0, resolution) * samples);

float get_i_1(){
  value_1 = 0;

  analogRead(BNC1);

  for (int i=0; i<samples; i++){
    value_1 += analogRead(BNC1);
  }

  curr_1 = value_1 * scaling;

  return curr_1;
}

float get_i_2(){
  value_2 = 0;

  analogRead(BNC2);

  for (int i=0; i<samples; i++){
    value_2 += analogRead(BNC2);
  }

  curr_2 = value_2 * scaling;

  return curr_2;
}

void dummySetFunc(float set_value){
  //Serial.println("Called the dummy function!");
}

using mist1::com1::Channel;
MakeChannelMap(lookup, 2, ({
    Channel{ 'i', 1, &get_i_1, &dummySetFunc},
    Channel{ 'i', 2, &get_i_2, &dummySetFunc},
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

mist1::com1::SerialDevice<128, 2> device(io_ctx, lookup);


void setup()   { 
  Serial.begin(115200);
  // Reported by the identity query "I", so the IOC can check what is on this port
  device.set_identity("Teensy_Ammeter", __DATE__);
  analogReadAveraging(32);
  analogReadResolution(16);
  /*
  com.add_channel(mist1::Channel("BNC1_CURR", 'i', 1, &dummyFunc, &get_i_1));
  com.add_channel(mist1::Channel("BNC2_CURR", 'i', 2, &dummyFunc, &get_i_2));
  */
}

void loop() {
 
  // GUI Communication.
  // Handles at most one complete command per pass and never waits for more input.
  // service() also runs the optional streaming ("P<ms>") and communication timeout.
  device.service(millis());
}

