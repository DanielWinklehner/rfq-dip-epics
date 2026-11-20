// libcom1 over TCP instead of USB serial.
//
// Written for the Arduino Opta (built-in Ethernet, Mbed core). The same pattern works on any board
// with the Arduino Ethernet API (EthernetServer / EthernetClient).
//
// STATUS: compiles against the Arduino Opta core (ArduinoCore-mbed) with the Opta's compiler
// settings, but has NOT YET BEEN RUN ON HARDWARE. Treat it as a starting point.
//
// On the EPICS side only the port changes, protocol file and records stay as they are:
//
//   drvAsynIPPortConfigure("OPTA1", "192.168.1.50:5025")
//   dbLoadRecords("db/mydevice.db", "PORT='OPTA1',DEVICE=opta1")
//
// Put the devices on a private control network: the protocol has no authentication.

#include <Ethernet.h>
#include <libcom1.hpp>

// ---- Network settings ---------------------------------------------------------------------------
IPAddress ip(192, 168, 1, 50);
const uint16_t PORT = 5025;

EthernetServer server(PORT);
EthernetClient client;   // one control system connection at a time

// ---- Channels -----------------------------------------------------------------------------------
// Opta: D0..D3 are the four relay outputs, A0..A7 the inputs.
const int relayPins[] = { D0, D1, D2, D3 };
const int inputPins[] = { A0, A1, A2, A3 };
bool relayStates[] = { false, false, false, false };

void set_relay(uint8_t i, float value) {
  relayStates[i] = (value == 1.0f);
  digitalWrite(relayPins[i], relayStates[i] ? HIGH : LOW);
}

float get_relay(uint8_t i) {
  return relayStates[i] ? 1.0f : 0.0f;
}

// Raw ADC counts. Convert to volts in the EPICS record (LINR/ESLO) or here.
float get_input(uint8_t i) {
  return (float)analogRead(inputPins[i]);
}

using mist1::com1::IndexedChannel;

MakeChannelMap(lookup, 8, ({
    IndexedChannel('r', 1, &get_relay, &set_relay, 0),
    IndexedChannel('r', 2, &get_relay, &set_relay, 1),
    IndexedChannel('r', 3, &get_relay, &set_relay, 2),
    IndexedChannel('r', 4, &get_relay, &set_relay, 3),
    IndexedChannel('a', 1, &get_input, nullptr, 0),
    IndexedChannel('a', 2, &get_input, nullptr, 1),
    IndexedChannel('a', 3, &get_input, nullptr, 2),
    IndexedChannel('a', 4, &get_input, nullptr, 3),
  })
);

// ---- Transport ----------------------------------------------------------------------------------
// Big enough for streaming: mist1::com1::min_stream_buffer_size(8) is 131
const size_t OUT_SIZE = 160;

mist1::com1::LineBuffer<128> rx;
char tx_line[OUT_SIZE + 1];

mist1::com1::IOHandler<OUT_SIZE> io_ctx(
    // Read: one complete line from the client, or an empty string if there is none yet
    []() -> char* {
      while (client && client.available() > 0) {
        if (rx.feed((char)client.read()))
          return rx.take();
      }
      return rx.none();
    },
    // Write: the reply and its line feed go out in ONE write.
    // Two writes become two TCP segments, and the second one can be held back for tens of
    // milliseconds (Nagle's algorithm on this side meeting delayed ACK on the other).
    [](char* str) {
      size_t n = strlen(str);
      if (n > OUT_SIZE)
        n = OUT_SIZE;
      memcpy(tx_line, str, n);
      tx_line[n] = '\n';
      if (client && client.connected())
        client.write((const uint8_t*)tx_line, n + 1);
    }
);

mist1::com1::SerialDevice<OUT_SIZE, 8> device(io_ctx, lookup);

// Safe state when the control system stops talking: all relays off.
void relays_off() {
  for (uint8_t i = 0; i < 4; ++i)
  { set_relay(i, 0.0f); }
}

void setup() {
  for (uint8_t i = 0; i < 4; ++i) {
    pinMode(relayPins[i], OUTPUT);
    digitalWrite(relayPins[i], LOW);
  }

  Ethernet.begin(ip);
  server.begin();

  device.set_identity("EthernetExample", __DATE__);

  // No valid command for 5 s: relays off. The IOC polls much faster than that.
  // When you only use streaming, let the IOC send "I" every few seconds as a heartbeat.
  device.set_comm_timeout(5000, &relays_off);
}

void loop() {
  // Take a new connection when there is none. A reconnecting IOC replaces a dead connection.
  EthernetClient incoming = server.accept();
  if (incoming) {
    if (client)
      client.stop();
    client = incoming;
    rx.reset();            // forget a half received line of the old connection
    device.set_stream_period(0);
  }

  device.service(millis());
}
