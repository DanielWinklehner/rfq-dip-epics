// R4 a: the decision of door_logic.hpp (D4 to D6), with the time given by the test.

#include <stdint.h>
#include "check.hpp"
#include "../door_logic.hpp"

using interlock_opta::DoorLogic;

static const uint32_t HOLD = 1000;

// Both doors as reported and the relays, in one call
static bool state_is(const DoorLogic& d, bool door1, bool door2)
{
  return d.reported_closed(0) == door1 && d.reported_closed(1) == door2 &&
         d.interlock_on() == (door1 && door2);
}

// Feed the same levels every millisecond from `from` to `to` (both included)
static void hold_levels(DoorLogic& d, bool c1, bool c2, uint32_t from, uint32_t to)
{
  for (uint32_t t = from;; ++t) {
    d.update(c1, c2, t);
    if (t == to)
      break;
  }
}

static void test_power_on()
{
  // reported open before the first reading and until the hold time has passed
  DoorLogic d(HOLD);
  CHECK(state_is(d, false, false));
  d.update(true, true, 5000);                       // first reading, millis() is not 0 here
  CHECK(state_is(d, false, false));
  hold_levels(d, true, true, 5001, 5000 + HOLD - 1);
  CHECK(state_is(d, false, false));
  d.update(true, true, 5000 + HOLD);
  CHECK(state_is(d, true, true));

  // the same with sparse readings: the first reading starts the wait, not the construction
  DoorLogic s(HOLD);
  s.update(true, true, 0);
  s.update(true, true, HOLD - 1);
  CHECK(state_is(s, false, false));
  s.update(true, true, HOLD);
  CHECK(state_is(s, true, true));
}

static void test_both_closed_after_hold()
{
  DoorLogic d(HOLD);
  hold_levels(d, true, true, 0, HOLD);
  CHECK(state_is(d, true, true));
  hold_levels(d, true, true, HOLD + 1, 10 * HOLD);
  CHECK(state_is(d, true, true));
}

static void test_each_door_alone_open()
{
  for (int door = 0; door < 2; ++door) {
    DoorLogic d(HOLD);
    hold_levels(d, true, true, 0, 2 * HOLD);
    CHECK(state_is(d, true, true));
    bool c1 = door != 0, c2 = door != 1;
    d.update(c1, c2, 2 * HOLD + 1);                  // the reading that sees the door open
    CHECK(state_is(d, c1, c2));
    CHECK(!d.interlock_on());
    hold_levels(d, c1, c2, 2 * HOLD + 2, 5 * HOLD);  // open for a while: stays reported open
    CHECK(state_is(d, c1, c2));
    // closed again: still reported open until the hold time has passed, then closed
    hold_levels(d, true, true, 5 * HOLD + 1, 6 * HOLD);
    CHECK(state_is(d, c1, c2));
    d.update(true, true, 6 * HOLD + 1);
    CHECK(state_is(d, true, true));
  }
}

static void test_one_millisecond_opening()
{
  DoorLogic d(HOLD);
  hold_levels(d, true, true, 0, 3000);
  CHECK(state_is(d, true, true));
  d.update(false, true, 3001);                       // open for exactly one reading
  CHECK(state_is(d, false, true));
  // closed again from 3002 on: reported open (relays off) for the full hold time after that
  hold_levels(d, true, true, 3002, 3002 + HOLD - 1);
  CHECK(state_is(d, false, true));
  d.update(true, true, 3002 + HOLD);
  CHECK(state_is(d, true, true));
}

static void test_bouncing_closing()
{
  // door 2 bounces for 40 ms (closed 3 ms, open 2 ms ...) and then stays closed from 10040
  DoorLogic d(HOLD);
  hold_levels(d, true, false, 0, 10000);
  CHECK(state_is(d, true, false));
  for (uint32_t t = 10001; t < 10040; ++t) {
    d.update(true, (t % 5) < 3, t);
    CHECK(state_is(d, true, false));                 // never reported closed while bouncing
  }
  hold_levels(d, true, true, 10040, 10040 + HOLD - 1);
  CHECK(state_is(d, true, false));
  d.update(true, true, 10040 + HOLD);
  CHECK(state_is(d, true, true));
}

static void test_wrap_in_the_middle_of_a_hold()
{
  // the wait starts 300 ms before the 32-bit millisecond counter wraps
  const uint32_t start = 0xFFFFFFFFu - 299u;         // 300 readings before 0
  DoorLogic d(HOLD);
  d.update(true, true, start);
  uint32_t t = start;
  for (uint32_t i = 1; i < HOLD; ++i) {
    t = start + i;                                   // wraps through 0
    d.update(true, true, t);
    CHECK_MSG(state_is(d, false, false), "t=%lu", (unsigned long)t);
  }
  CHECK(t == HOLD - 301);                            // the counter did wrap
  d.update(true, true, start + HOLD);                // = 700 after the wrap
  CHECK(state_is(d, true, true));

  // and a door that opens after the wrap is still seen
  d.update(false, true, start + HOLD + 5);
  CHECK(state_is(d, false, true));
}

static void test_opening_exactly_at_the_end_of_the_hold()
{
  DoorLogic d(HOLD);
  hold_levels(d, true, true, 100, 100 + HOLD - 1);
  CHECK(state_is(d, false, false));
  // the reading at the very moment the hold time ends says "open" for door 2: door 1 is now
  // reported closed, door 2 is not, the relays stay off
  d.update(true, false, 100 + HOLD);
  CHECK(state_is(d, true, false));
  d.update(true, true, 100 + HOLD + 1);              // the wait starts again for door 2
  CHECK(state_is(d, true, false));
  hold_levels(d, true, true, 100 + HOLD + 2, 100 + 2 * HOLD);
  CHECK(state_is(d, true, false));
  d.update(true, true, 100 + 2 * HOLD + 1);
  CHECK(state_is(d, true, true));
}

int main()
{
  test_power_on();
  test_both_closed_after_hold();
  test_each_door_alone_open();
  test_one_millisecond_opening();
  test_bouncing_closing();
  test_wrap_in_the_middle_of_a_hold();
  test_opening_exactly_at_the_end_of_the_hold();
  return finish("door logic");
}
