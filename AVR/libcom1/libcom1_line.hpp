#ifndef e53ab5d5_libcom1_line_h
#define e53ab5d5_libcom1_line_h

#include <stddef.h>

namespace mist1 {

namespace com1 {

// Collects received characters into complete, NUL-terminated lines without ever blocking.
//
// Why this exists: reading with Serial.readBytesUntil() has two problems.
//  1. It does not NUL-terminate, so a short command inherits the tail of the previous longer one
//     ("sa1100" followed by "sa15" was parsed as 500).
//  2. It waits for the Stream timeout (1 s by default) when a line never ends, so a single stray
//     byte stalls loop(), and with it whatever else the sketch is doing.
//
// Usage as the read function of an IOHandler:
//
//   mist1::com1::LineBuffer<128> rx;
//   ...
//   [](){
//     while (Serial.available() > 0) {
//       if (rx.feed((char)Serial.read()))
//         return rx.take();
//     }
//     return rx.none();   // no complete line yet: SerialDevice does nothing
//   }
//
// Behaviour:
//  - '\n' ends a line, '\r' is dropped, so LF and CR LF senders both work.
//  - Empty lines are ignored.
//  - A line longer than N - 1 characters is discarded as a whole and reported as the line "!",
//    which SerialDevice answers with ERR0. A truncated command is never executed.
template <size_t N>
class LineBuffer
{
  static_assert(N >= 8, "LineBuffer is too small to hold a command");

  char m_buf[N];
  size_t m_len;
  bool m_overflow;
  char m_none[1];

public:
  LineBuffer() : m_buf{0}, m_len(0), m_overflow(false), m_none{0} {}

  // Feed one received character.
  // Returns true when a complete line is ready; fetch it with take() before feeding again.
  bool feed(char c)
  {
    if (c == '\n') {
      if (m_overflow) {
        m_overflow = false;
        m_len = 0;
        m_buf[0] = '!';
        m_buf[1] = '\0';
        return true;
      }
      m_buf[m_len] = '\0';
      const bool has_content = (m_len != 0);
      m_len = 0;
      return has_content;
    }

    if (c == '\r' || m_overflow)
      return false;

    if (m_len + 1 >= N) {
      // Too long: drop everything up to the next '\n'
      m_overflow = true;
      m_len = 0;
      return false;
    }

    m_buf[m_len++] = c;
    return false;
  }

  // The completed line. Valid until the next call to feed().
  char* take()
  {
    return m_buf;
  }

  // An empty string, meaning "nothing to process".
  char* none()
  {
    m_none[0] = '\0';
    return m_none;
  }

  // Forget a partially received line (for example after a client disconnects).
  void reset()
  {
    m_len = 0;
    m_overflow = false;
  }
};

} // namespace com1

} // namespace mist1

#endif // e53ab5d5_libcom1_line_h
