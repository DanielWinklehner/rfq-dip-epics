#ifndef interlock_opta_door_logic_hpp
#define interlock_opta_door_logic_hpp

// The interlock decision of InterlockOpta, without pins and without a clock: it gets the two
// door states as read from the inputs and the time in milliseconds, and gives the doors as
// they are reported and the state of the interlock relays. Tested on a PC (tests/).
//
//  - An input that reads open makes its door reported open at once.
//  - A door is reported closed only after its input has read closed without interruption for
//    hold_ms. Every reading of "open" in between starts the wait again. So an opening that
//    is shorter than the IOC's poll period (100 ms) or a bouncing switch is reported for at
//    least hold_ms, and the IOC sees it.
//  - After power-on (construction) both doors are reported open until the hold time has
//    passed.
//  - The interlock relays are on only while both doors are reported closed. Nothing else
//    switches them: this class has no setter, and the device of interlock_device.hpp has no
//    channel for them.
//  - No latch: when both doors are closed again (after the hold time) the relays come back on.
//
// Time is a uint32_t of milliseconds (millis()) and wraps after 49.7 days. Only differences
// `now - since` are used, which are correct across the wrap as long as one wait is shorter
// than 49.7 days.

#include <stdint.h>

namespace interlock_opta {

class DoorLogic {
public:
  static constexpr uint8_t DOORS = 2;

  explicit DoorLogic(uint32_t hold_ms)
    : m_hold_ms(hold_ms), m_reported_closed{false, false}, m_counting{false, false},
      m_since{0, 0}
  {}

  // One reading of both inputs at time now_ms. closed1, closed2: the input reads "door closed".
  void update(bool closed1, bool closed2, uint32_t now_ms)
  {
    update_door(0, closed1, now_ms);
    update_door(1, closed2, now_ms);
  }

  // The door as reported to the IOC (channel i1 / i2): true = closed.
  bool reported_closed(uint8_t door) const
  {
    return door < DOORS && m_reported_closed[door];
  }

  // Interlock relays 1 and 2.
  bool interlock_on() const
  {
    return m_reported_closed[0] && m_reported_closed[1];
  }

  uint32_t hold_ms() const { return m_hold_ms; }

private:
  void update_door(uint8_t door, bool closed, uint32_t now_ms)
  {
    if (!closed) {
      m_reported_closed[door] = false;
      m_counting[door] = false;
      return;
    }
    if (!m_counting[door]) {
      m_counting[door] = true;
      m_since[door] = now_ms;
    }
    // unsigned difference: correct across the wrap of the millisecond counter
    if (!m_reported_closed[door] && static_cast<uint32_t>(now_ms - m_since[door]) >= m_hold_ms)
      m_reported_closed[door] = true;
  }

  uint32_t m_hold_ms;
  bool m_reported_closed[DOORS];
  bool m_counting[DOORS];       // the input has read closed since m_since without interruption
  uint32_t m_since[DOORS];
};

} // namespace interlock_opta

#endif // interlock_opta_door_logic_hpp
