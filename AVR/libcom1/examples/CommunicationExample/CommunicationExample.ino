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

using mist1::com1::Channel;

// lookup is the variable name,
// 3 is the size of the array, this must match the number of Channels that are being defined
// the rest is the channels in the map
// A channel without a setter (nullptr) is read-only, one without a getter is write-only.
// For many similar channels see mist1::com1::IndexedChannel (used in devices/SolenoidValveBox).
MakeChannelMap(lookup, 3, ({
    Channel{ 'd', 1, &d1_get, &d1_set },
    Channel{ 'd', 2, &d2_get, &d2_set },
    Channel{ 'a', 1, &a1_get, nullptr },
  })
);

// Collects the received characters into complete lines.
// It never blocks and always NUL-terminates, which Serial.readBytesUntil() does not:
// with that, "sa1100" followed by "sa15" was read as "sa1500".
mist1::com1::LineBuffer<128> serial_in_buffer;

// Template parameter is buffer size for the output buffer.
// It needs at least 14 bytes per channel plus 2 (mist1::com1::min_out_buffer_size), and
// 17 more to use streaming. SerialDevice refuses to compile if it is too small.
mist1::com1::IOHandler<128> io_ctx(
    // Read from the serial port.
    // Returns one complete line, or an empty string while there is none: the device then
    // simply does nothing on this pass of loop().
    []() -> char* {
      while (Serial.available() > 0) {
        if (serial_in_buffer.feed((char)Serial.read()))
          return serial_in_buffer.take();
      }
      return serial_in_buffer.none();
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

// A safe state for the outputs, used by the communication timeout below
void outputs_off() {
  digitalWrite(45, LOW);
  digitalWrite(30, LOW);
}

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

  // Name and firmware version reported by the identity query "I"
  device.set_identity("CommunicationExample", __DATE__);

  // Optional: switch the outputs off when no valid command has arrived for 5 seconds,
  // for example because the IOC went away. Decide per device what "safe" means.
  // device.set_comm_timeout(5000, &outputs_off);
}

void loop() {
  // service() processes at most one received command and returns immediately otherwise,
  // so loop() stays free for the real work of the device (interlocks, regulation, ...).
  // It also runs everything that needs the time: streaming ("P<ms>", for EPICS I/O Intr
  // records) and the communication timeout.
  //
  // device.communicate() does the same without the time dependent parts.
  // device.intr_communicate() is the old I/O Intr mode: it sends all channels on every
  // call without input, as fast as loop() runs. Streaming replaces it.

  device.service(millis());
}
