#ifndef interlock_opta_tests_box_hpp
#define interlock_opta_tests_box_hpp

// The PC build of InterlockOpta: interlock_device.hpp with the transport of the sketch replaced
// by a line in memory. A received line goes through LineBuffer as on the board (character by
// character, with its line feed); every reply is kept. The loop of the sketch is step():
// read the inputs, service() the device once.

#include <stdint.h>
#include <string.h>
#include "../interlock_device.hpp"

namespace box {

using namespace interlock_opta;

static const char* FIRMWARE = "Nov 21 2026";    // stands for __DATE__; the placeholder of the simulator

static mist1::com1::LineBuffer<IN_BUFFER> g_rx;
static const char* g_pending = nullptr;        // line to deliver (without its line feed)
static size_t g_pending_pos = 0;
static bool g_pending_lf = false;

static char g_replies[8][OUT_BUFFER + 1];
static int g_reply_count = 0;

static char* transport_read()
{
  // As the sketch: hand the characters to LineBuffer until a line is complete
  while (g_pending != nullptr) {
    char c;
    if (g_pending[g_pending_pos] != '\0') {
      c = g_pending[g_pending_pos++];
    } else if (g_pending_lf) {
      c = '\n';
      g_pending = nullptr;
    } else {
      g_pending = nullptr;
      break;
    }
    if (g_rx.feed(c))
      return g_rx.take();
  }
  return g_rx.none();
}

static void transport_write(char* line)
{
  if (g_reply_count < 8) {
    strncpy(g_replies[g_reply_count], line, OUT_BUFFER);
    g_replies[g_reply_count][OUT_BUFFER] = '\0';
  }
  ++g_reply_count;
}

static mist1::com1::IOHandler<OUT_BUFFER> io(&transport_read, &transport_write);
static mist1::com1::SerialDevice<OUT_BUFFER, CHANNELS> device(io, channels);

static void power_on()
{
  reset_state();
  g_rx.reset();
  g_pending = nullptr;
  g_reply_count = 0;
  device.set_identity(IDENTITY, FIRMWARE);
}

// One pass of loop() at time now_ms with the two input levels and, optionally, a received line
// (nullptr: nothing received). Returns the number of replies; they are in g_replies.
static int step(uint32_t now_ms, bool level_i1, bool level_i2, const char* line)
{
  g_reply_count = 0;
  g_pending = line;
  g_pending_pos = 0;
  g_pending_lf = true;
  update_inputs(level_i1, level_i2, now_ms);
  device.service(now_ms);
  return g_reply_count;
}

} // namespace box

#endif
