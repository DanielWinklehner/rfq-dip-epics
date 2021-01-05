#include <stdio.h>
#include <libcom1.hpp>

// Enable printf on Serial support
#define ENABLE_PRINTF 0


#if ENABLE_PRINTF
PRINTF_SERIAL_PREINIT();
#endif

float d1_get() {
  return digitalRead(50);
}

void d1_set(float setval) {
  digitalWrite(45, (int)(setval));
}

float d2_get() {
  return digitalRead(40);
}

void d2_set(float setval) {
  digitalWrite(30, (int)(setval));
}

float a1_get() {
  const auto freq = 0.1/1000.0*2.0*PI;
  return sin( freq * millis() );
}

void dummy_set(float setval) {
}

using mist1::com1::Channel;

// lookup is the variable name,
// 3 is the size of the array, this must match the number of Channels that are being defined
// the rest is the channels in the map
MakeChannelMap(lookup, 3, ({
    Channel{ 'd', 1, &d1_get, &d1_set },
    Channel{ 'd', 2, &d2_get, &d2_set },
    Channel{ 'a', 1, &a1_get, &dummy_set },
  })
);

char serial_in_buffer[128]{0};

// Template parameter is buffer size for the output buffer
mist1::com1::IOHandler<128> io_ctx(
    // Read from the serial port
    [](){
      // Blocking Example ------------------------------------
      while (Serial.available() == 0)                       //
      { asm volatile("nop"); }                              //
                                                            //
      Serial.readBytesUntil('\n', serial_in_buffer, 128);   //
      
      // Non-blocking example --------------------------------
//    if (Serial.available() == 0)                          //
//      serial_in_buffer[0] = '\0';                         //
//    else                                                  //
//      Serial.readBytesUntil('\n', serial_in_buffer, 128); //
      
      return serial_in_buffer;
    },
    // Write to the serial port
    [](char* str){
#if ENABLE_PRINTF
      printf("%s\n", str);
#else
      Serial.println(str);
#endif
    }
);

// Template parameters must match the above!
mist1::com1::SerialDevice<128, 3> device(io_ctx, lookup);

void setup() {
  // Pin setup
  pinMode(45, OUTPUT);
  pinMode(50, INPUT);
  pinMode(30, OUTPUT);
  pinMode(40, INPUT);

  // Enable USART
  Serial.begin(9600);

#if ENABLE_PRINTF
  PRINTF_SERIAL_INIT();
#endif
}

void loop() {
  // device.communicate() is for polling communication

  // device.intr_communicate(delayms) is for EPICS IO Interrupt Mode communication
  // It wouldn't be a bad idea to put a delay here w/ intr_communicate mode
  // In addition, the read function in the IOHandler constructor must be non-blocking
  // and return a null byte '\0' when there is no serial data to read.

  device.communicate();
}
