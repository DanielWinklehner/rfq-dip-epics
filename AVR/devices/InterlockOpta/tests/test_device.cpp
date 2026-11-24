// R4 b: InterlockOpta through libcom1, as a conversation of lines in and lines out.

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "check.hpp"
#include "box.hpp"

using namespace interlock_opta;

static uint32_t g_now = 0;

// Send one line with both doors at the given levels; returns the single reply or "" if none.
static const char* say(const char* line, bool i1 = true, bool i2 = true)
{
  int n = box::step(++g_now, i1, i2, line);
  return n == 0 ? "" : box::g_replies[0];
}

// Time passes with the given levels, no line received
static void wait_ms(uint32_t ms, bool i1 = true, bool i2 = true)
{
  for (uint32_t i = 0; i < ms; ++i)
    box::step(++g_now, i1, i2, nullptr);
}

static bool relays_are(bool r1, bool r2, bool r3, bool r4)
{
  return relay_on(0) == r1 && relay_on(1) == r2 && relay_on(2) == r3 && relay_on(3) == r4;
}

static void start(bool closed)
{
  box::power_on();
  g_now = 1000;
  wait_ms(HOLD_MS + 1, closed, closed);
}

static void test_identity_and_channels()
{
  start(true);
  CHECK(strcmp(say("I"), "oID=InterlockOpta;FW=Nov 21 2026;PROTO=2;CH=i1,i2,s1,s2") == 0);
  printf("  I -> %s\n", box::g_replies[0]);
}

static void test_query_all_order()
{
  start(true);
  CHECK(strcmp(say("A"), "o1:1:0:0") == 0);
  CHECK(strcmp(say("Ss21"), "ok") == 0);
  CHECK(strcmp(say("A"), "o1:1:0:1") == 0);            // i1, i2, s1, s2
  CHECK(strcmp(say("A", false, true), "o0:1:0:1") == 0);
  CHECK(strcmp(say("A", true, true), "o0:1:0:1") == 0); // door 1 waits for its hold time
  wait_ms(HOLD_MS);
  CHECK(strcmp(say("A", true, false), "o1:0:0:1") == 0);
  printf("  A -> %s\n", box::g_replies[0]);
  // power-on: everything open and off
  box::power_on();
  CHECK(strcmp(say("A"), "o0:0:0:0") == 0);
}

static void test_spare_relays()
{
  start(true);
  CHECK(relays_are(true, true, false, false));
  CHECK(strcmp(say("Ss11"), "ok") == 0);
  CHECK(relays_are(true, true, true, false));
  CHECK(strcmp(say("gs1"), "o1") == 0);
  CHECK(strcmp(say("ss21"), "") == 0);                   // unacknowledged set: no reply
  CHECK(relays_are(true, true, true, true));
  CHECK(strcmp(say("gs2"), "o1") == 0);
  CHECK(strcmp(say("Ss12"), "ok") == 0);                 // anything but exactly 1 is off
  CHECK(relays_are(true, true, false, true));
  CHECK(strcmp(say("Ss20.999"), "ok") == 0);
  CHECK(relays_are(true, true, false, false));
  CHECK(strcmp(say("gs1"), "o0") == 0);
  CHECK(strcmp(say("Ss21e0"), "ok") == 0);
  CHECK(strcmp(say("gs2"), "o1") == 0);
  // the spare relays do not depend on the doors
  CHECK(strcmp(say("A", false, false), "o0:0:0:1") == 0);
  CHECK(relays_are(false, false, false, true));
}

static void test_set_of_a_door_is_accepted_and_ignored()
{
  start(true);
  CHECK(strcmp(say("Si10"), "ok") == 0);
  CHECK(strcmp(say("gi1"), "o1") == 0);
  CHECK(strcmp(say("si20"), "") == 0);
  CHECK(strcmp(say("gi2"), "o1") == 0);
  CHECK(relays_are(true, true, false, false));
  start(false);
  CHECK(strcmp(say("Si11", false, false), "ok") == 0);
  CHECK(strcmp(say("gi1", false, false), "o0") == 0);
  CHECK(relays_are(false, false, false, false));
}

static void test_errors()
{
  start(true);
  CHECK(strcmp(say("gr1"), "ERR4") == 0);
  CHECK(strcmp(say("Si1abc"), "ERR5") == 0);
  CHECK(strcmp(say("x"), "ERR0") == 0);
  CHECK(strcmp(say("q01i10"), "oi1+10+") == 0);         // legacy query of the old box
}

// No line whatsoever switches relays 1 and 2: every command of the README against every
// channel name and against names that do not exist, then random lines, in both door states.
static const char* const COMMANDS[] = { "s", "S", "g", "q01", "P", "A", "I" };
static const char* const NAMES[] = {
  "i1", "i2", "s1", "s2",                                 // the channels
  "s3", "s4", "i3", "r1", "r2", "R1", "d0", "d1", "o1", "o2", "x9", "a1", "\x01\x01", "1i",
  "", "i", "s",
};
static const char* const VALUES[] = {
  "", "0", "1", "1.0", "-1", "2", "0.5", "1e9", "-0", "nan", "inf", "-inf", "abc", "1x",
  " 1", "1 ", "100", "0x1",
};

static int g_lines = 0;

static void check_line(const char* line, bool doors_closed)
{
  box::step(++g_now, doors_closed, doors_closed, line);
  ++g_lines;
  CHECK_MSG(relay_on(0) == doors_closed && relay_on(1) == doors_closed,
            "line \"%s\" with doors %s: relay 1 %d, relay 2 %d", line ? line : "(tick)",
            doors_closed ? "closed" : "open", relay_on(0), relay_on(1));
}

static void test_no_line_switches_the_interlock_relays()
{
  char line[160];
  for (int closed = 0; closed < 2; ++closed) {
    start(closed != 0);
    for (const char* cmd : COMMANDS)
      for (const char* name : NAMES)
        for (const char* value : VALUES) {
          snprintf(line, sizeof(line), "%s%s%s", cmd, name, value);
          check_line(line, closed != 0);
          // the same with a legacy precision digit
          snprintf(line, sizeof(line), "%s%s%s3", cmd, name, value);
          check_line(line, closed != 0);
        }
    // streaming on and off, with time passing
    check_line("P10", closed != 0);
    for (int i = 0; i < 50; ++i)
      check_line(nullptr, closed != 0);
    check_line("P0", closed != 0);
    // random lines of any byte but NUL and line feed, up to 140 characters (longer than the
    // input buffer, which discards them).
    // Bytes 0x80 to 0xFF too, with signed and with unsigned char: this test found that
    // libcom1's i16u_iden() shifted a negative value left for such a byte as the channel
    // letter where char is signed (fixed in the library, with a test of its own).
    const uint32_t BYTES = 255;
    uint32_t x = 12345u + (uint32_t)closed;
    for (int n = 0; n < 20000; ++n) {
      x = x * 1103515245u + 12345u;
      size_t len = 1 + (x >> 16) % 140;
      for (size_t k = 0; k < len; ++k) {
        x = x * 1103515245u + 12345u;
        char c = (char)(1 + (x >> 16) % BYTES);
        line[k] = (c == '\n') ? 'n' : c;
      }
      line[len] = '\0';
      check_line(line, closed != 0);
    }
    CHECK(relays_are(closed != 0, closed != 0, relay_on(2), relay_on(3)));
  }
  printf("  %d lines sent, relays 1 and 2 followed the doors after every one\n", g_lines);
}

int main()
{
  test_identity_and_channels();
  test_query_all_order();
  test_spare_relays();
  test_set_of_a_door_is_accepted_and_ignored();
  test_errors();
  test_no_line_switches_the_interlock_relays();
  return finish("device");
}
