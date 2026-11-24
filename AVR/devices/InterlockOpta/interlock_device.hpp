#ifndef interlock_opta_interlock_device_hpp
#define interlock_opta_interlock_device_hpp

// The device InterlockOpta as the IOC sees it, without pins and without Serial: the channel map
// of the old interlock box (AVR/devices/InterlockBox) on top of the door logic. The sketch
// (InterlockOpta.ino) and the PC tests (tests/) include this header once each; it holds the
// state of the device in variables of this one translation unit.
//
// Channels, in this order (the order of the "A" reply, EPICS/Db/interlockbox.db):
//   i1, i2  the doors as reported by DoorLogic: 1 = closed, 0 = open. A set is accepted and
//           does nothing, as in the old box (its dummySetFunc).
//   s1, s2  two spare relays (Opta relays 3 and 4): a set of exactly 1 switches on, any other
//           number off, as set_solenoid1/2 of the old box; read back as 1 or 0.
// Relays 1 and 2 (the interlock contacts) have no channel. They follow DoorLogic only.

#include <stdint.h>
#include <libcom1.hpp>
#include "door_logic.hpp"

namespace interlock_opta {

// ---- Constants ----------------------------------------------------------------------------------

// D6: a door is reported closed (and the interlock relays may switch on) only after its input
// has read closed for this long without interruption. The IOC polls every 100 ms.
constexpr uint32_t HOLD_MS = 1000;

// D5, ASSUMED: the switch closes when the door closes and feeds the input from the Opta's own
// supply, so the input reads HIGH (true) for a closed door. A broken wire or a switch without
// supply then reads LOW = door open. Setting one of these to false reads that input the other
// way round, and a broken wire would then count as a CLOSED door (see README.md).
constexpr bool DOOR1_CLOSED_LEVEL = true;   // input I1
constexpr bool DOOR2_CLOSED_LEVEL = true;   // input I2

// Identity reported by "I" (the firmware version is __DATE__, given by the sketch)
constexpr const char* IDENTITY = "InterlockOpta";

// Output buffer of IOHandler / SerialDevice: 128 as in the old box. min_out_buffer_size(4) = 58,
// min_stream_buffer_size(4) = 75.
constexpr size_t OUT_BUFFER = 128;
constexpr size_t IN_BUFFER = 128;            // LineBuffer: lines up to 127 characters
constexpr size_t CHANNELS = 4;

// The four relays of the Opta, in the order of their terminals
constexpr uint8_t RELAYS = 4;
constexpr uint8_t RELAY_INTERLOCK_1 = 0;     // relay 1
constexpr uint8_t RELAY_INTERLOCK_2 = 1;     // relay 2
constexpr uint8_t RELAY_SPARE_1 = 2;         // relay 3, channel s1
constexpr uint8_t RELAY_SPARE_2 = 3;         // relay 4, channel s2

// ---- State --------------------------------------------------------------------------------------

static DoorLogic g_doors(HOLD_MS);
static bool g_spare[2] = { false, false };

// ---- Channel callbacks --------------------------------------------------------------------------

inline float get_door(uint8_t door)
{
  return g_doors.reported_closed(door) ? 1.0f : 0.0f;
}

// Accepted and ignored: the doors are inputs.
inline void set_door_ignored(uint8_t, float) {}

inline float get_spare(uint8_t i)
{
  return (i < 2 && g_spare[i]) ? 1.0f : 0.0f;
}

inline void set_spare(uint8_t i, float value)
{
  if (i < 2)
    g_spare[i] = (value == 1.0f);
}

using mist1::com1::IndexedChannel;
MakeChannelMap(channels, 4, ({
    IndexedChannel('i', 1, &get_door, &set_door_ignored, 0),
    IndexedChannel('i', 2, &get_door, &set_door_ignored, 1),
    IndexedChannel('s', 1, &get_spare, &set_spare, 0),
    IndexedChannel('s', 2, &get_spare, &set_spare, 1),
  })
);

// ---- What the sketch calls ----------------------------------------------------------------------

// One reading of the two inputs (true = HIGH) at time now_ms.
inline void update_inputs(bool level_i1, bool level_i2, uint32_t now_ms)
{
  g_doors.update(level_i1 == DOOR1_CLOSED_LEVEL, level_i2 == DOOR2_CLOSED_LEVEL, now_ms);
}

// Whether relay `relay` (0 to 3 = relays 1 to 4) is to be on now.
inline bool relay_on(uint8_t relay)
{
  switch (relay) {
    case RELAY_INTERLOCK_1:
    case RELAY_INTERLOCK_2:
      return g_doors.interlock_on();
    case RELAY_SPARE_1:
      return g_spare[0];
    case RELAY_SPARE_2:
      return g_spare[1];
    default:
      return false;
  }
}

inline bool both_doors_closed() { return g_doors.interlock_on(); }

// Back to the state after power-on. For the PC tests; the sketch never calls it.
inline void reset_state()
{
  g_doors = DoorLogic(HOLD_MS);
  g_spare[0] = false;
  g_spare[1] = false;
}

} // namespace interlock_opta

#endif // interlock_opta_interlock_device_hpp
