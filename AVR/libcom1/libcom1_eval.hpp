#ifndef e53ab5d5_libcom1_eval_h
#define e53ab5d5_libcom1_eval_h

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <float.h>

#include "libcom1_com.hpp"

namespace mist1 {

namespace com1 {

namespace detail {

  // Written without <math.h> classification macros so they behave the same on every toolchain.
  inline bool is_nan(float v) { return v != v; }
  inline bool is_inf(float v) { return v > FLT_MAX || v < -FLT_MAX; }
  inline bool is_finite(float v) { return !is_nan(v) && !is_inf(v); }

  // True if the NUL-terminated string holds at least n characters.
  inline bool has_length(const char* str, size_t n)
  {
    for (size_t i = 0; i < n; ++i) {
      if (str[i] == '\0')
        return false;
    }
    return true;
  }

  // Writes `v` as text into `dst`, NUL-terminated, and returns the number of characters written.
  // `dst` must have room for MAX_VALUE_CHARS + 1 bytes.
  //
  // Not-a-number and infinities are written as "nan", "inf" and "-inf". They used to corrupt the
  // query-all reply on Arduino AVR, where the zero trimming below assumed a fixed-width number.
  inline uint8_t format_value(float v, char* dst)
  {
    if (is_nan(v)) {
      memcpy(dst, "nan", 4);
      return 3;
    }
    if (is_inf(v)) {
      if (v < 0) {
        memcpy(dst, "-inf", 5);
        return 4;
      }
      memcpy(dst, "inf", 4);
      return 3;
    }

#if LIBCOM1_USE_DTOSTRE
    // The Arduino IDE does not support any float-related printf's on AVR, so we use dtostre(),
    // which always gives "+d.dddddde+dd" (13 characters), and then remove the trailing zeros
    // of the fractional part: "+2.500000e+01" -> "+2.5e+01", "+2.000000e+01" -> "+2.e+01".
    dtostre(v, dst, 6, DTOSTR_ALWAYS_SIGN | DTOSTR_PLUS_SIGN);

    char* e_ptr = dst + 9;
    char* zero_start = e_ptr;
    while (zero_start != dst + 3 && *(zero_start - 1) == '0')
    { --zero_start; }

    // 1 for e, 1 for sign, 2 for power, 1 for the terminating NUL
    memmove(zero_start, e_ptr, 5);
    return static_cast<uint8_t>(13 - (e_ptr - zero_start));
#else
    int n = snprintf(dst, static_cast<size_t>(MAX_VALUE_CHARS) + 1, "%g", static_cast<double>(v));
    if (n < 0)
      n = 0;
    if (n > MAX_VALUE_CHARS)
      n = MAX_VALUE_CHARS; // cannot happen for a float, but never trust a length
    return static_cast<uint8_t>(n);
#endif
  }

} // namespace detail

template <size_t OutBufferSize>
class IOHandler
{
private:
  using InFunc = auto (*)(void) -> char*;
  using OutFunc = auto (*)(char*) -> void;

  InFunc m_infunc;
  OutFunc m_outfunc;
public:
  char* m_input;
  char m_outbuffer[OutBufferSize]{0};

  IOHandler (InFunc in, OutFunc out)
    : m_infunc(in), m_outfunc(out), m_input(nullptr)
  {
  }

  void read()
  {
    m_input = (*m_infunc)();
  }

  void write(char* str)
  {
     (*m_outfunc)(str);
  }


  void write_buffer()
  {
    (*m_outfunc)(m_outbuffer);
  }

  // Copies a short constant reply ("ok", "ERR4") into the output buffer and sends it.
  void write_text(const char* text)
  {
    size_t i = 0;
    for (; i + 1 < OutBufferSize && text[i] != '\0'; ++i)
    { m_outbuffer[i] = text[i]; }
    m_outbuffer[i] = '\0';
    write_buffer();
  }

#if __cplusplus >= 201703L
  template<typename... Args>
  void write_debug(const char* f, Args... args) {
    if constexpr (DEBUG)
    {
      printf(f, args...);
    } else {}
  }
#else
  // Pre C++17 does not have `if constexpr`, so here is some magic using
  // SFINAE to choose which function to compile depending on Comm::DEBUG
  template<bool check = DEBUG, typename... Args>
  typename stdx::enable_if<true == check>::type
  write_debug (const char * f, Args... args)
  {
    printf(f, args...);
  }

  // There is unwanted "unused-parameter" warning spam when DEBUG is disabled.
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"
  template<bool check = DEBUG, typename... Args>
  typename stdx::enable_if<false == check>::type
  write_debug (const char * f, Args... args)
  {}
#pragma GCC diagnostic pop

#endif // debug_printing
};

// Commands understood by a SerialDevice (one per line, see README.md for details):
//
//   A               query all channels            -> o<v1>:<v2>:...:<vN>
//   g<c><n>         query one channel             -> o<value>
//   s<c><n><value>  set one channel               -> (no reply on success)
//   S<c><n><value>  set one channel, acknowledged -> ok
//   I               identify                      -> oID=<name>;FW=<version>;PROTO=2;CH=<c1n1>,<c2n2>,...
//   P<ms>           stream all channels every <ms> milliseconds, 0 = off -> ok
//                   stream frames:                   t<seq>:<device ms>:<v1>:...:<vN>
//   q01<c><n><p>    legacy single query           -> o<c><n><sign><digits><exp><exp sign>
//
// Every failure is answered with ERR<n>.
template<size_t OutBufferSize, size_t ChannelMapSize>
class SerialDevice{
  static_assert(OutBufferSize >= min_out_buffer_size(ChannelMapSize),
                "libcom1: the output buffer is too small for a query-all reply. "
                "Give IOHandler and SerialDevice at least 14 bytes per channel plus 2.");
  static_assert(OutBufferSize >= 16, "libcom1: the output buffer must be at least 16 bytes");

public:
  using TimeoutFunc = void (*)();

  IOHandler<OutBufferSize>& m_io;
  const ChannelMap<ChannelMapSize>& m_map;

private:
  const char* m_name;
  const char* m_version;

  uint32_t m_now;
  uint32_t m_last_rx;
  uint32_t m_timeout_ms;
  TimeoutFunc m_on_timeout;

  uint32_t m_stream_period;
  uint32_t m_stream_next;
  uint16_t m_seq;

  bool m_clock_started;
  bool m_comm_lost;
  bool m_stream_primed;

public:
  SerialDevice(IOHandler<OutBufferSize>& io, const ChannelMap<ChannelMapSize>& channels)
    : m_io(io), m_map(channels),
      m_name("libcom1"), m_version("0"),
      m_now(0), m_last_rx(0), m_timeout_ms(0), m_on_timeout(nullptr),
      m_stream_period(0), m_stream_next(0), m_seq(0),
      m_clock_started(false), m_comm_lost(false), m_stream_primed(false)
  {}

  // --- Optional configuration -------------------------------------------------------------

  // Name and firmware version reported by the identity query "I".
  // Both strings must outlive the device (use string literals) and must not contain ';'.
  void set_identity(const char* name, const char* version)
  {
    m_name = name;
    m_version = version;
  }

  // Call `on_timeout` once when no valid command has arrived for `timeout_ms` milliseconds
  // (0 disables). Meant for driving outputs to a safe state when the control system goes away.
  // Only evaluated by service(), because it needs the time.
  void set_comm_timeout(uint32_t timeout_ms, TimeoutFunc on_timeout)
  {
    m_timeout_ms = timeout_ms;
    m_on_timeout = on_timeout;
    m_comm_lost = false;
  }

  // True from the moment the communication timeout expired until the next valid command.
  bool comm_lost() const
  {
    return m_comm_lost;
  }

  // Send all channels every `period_ms` milliseconds without being asked (0 = off).
  // Same as the "P<ms>" command. Only acted on by service().
  // Returns false if the output buffer cannot hold a stream frame, see min_stream_buffer_size().
  bool set_stream_period(uint32_t period_ms)
  {
    if (period_ms != 0 && OutBufferSize < min_stream_buffer_size(ChannelMapSize))
      return false;
    m_stream_period = period_ms;
    m_stream_primed = false;
    return true;
  }

  uint32_t stream_period() const
  {
    return m_stream_period;
  }

  // --- Main entry points ------------------------------------------------------------------

  // Function for the device to process the input and write an output.
  // Unacceptable inputs will output an error, elaborated in the README.
  // This function would be continuously run in a loop. If there's no input, there is no output.
  // Returns the PRC_* / ERR_* code of what happened.
  uint8_t communicate()
  {
    const uint8_t result = process_input();

    switch (result) {
      case PRC_QUERY:
      case PRC_QALL:
      case PRC_GET:
      case PRC_IDENT:
        m_io.write_buffer();
        break;

      case PRC_SET_ACK:
      case PRC_PERIOD:
        m_io.write_text("ok");
        break;

      case ERR_UNKNOWN:
        m_io.write_text("ERR0");
        break;

      case ERR_PRECISION_TOO_LARGE:
        m_io.write_text("ERR1");
        break;

      case ERR_BUFFER:
        m_io.write_text("ERR2");
        break;

      case ERR_NUM_CHANNELS:
        m_io.write_text("ERR3");
        break;

      case ERR_CHANNEL_LOOKUP:
        m_io.write_text("ERR4");
        break;

      case ERR_SYNTAX:
        m_io.write_text("ERR5");
        break;

      case ERR_VALUE:
        m_io.write_text("ERR6");
        break;

      case ERR_NOT_SUPPORTED:
        m_io.write_text("ERR7");
        break;

      case ERR_NO_DATA:
      case PRC_SET:
      default:
        break;
    }

    if (result < ERR_UNKNOWN) {
      // A valid command: the other side is alive
      m_last_rx = m_now;
      m_comm_lost = false;
    }

    return result;
  }

  // Like communicate(), plus everything that depends on time: streaming and the
  // communication timeout. Call it on every pass of loop() with the current time,
  // for example `device.service(millis());`. The read function must not block.
  uint8_t service(uint32_t now_ms)
  {
    m_now = now_ms;
    if (!m_clock_started) {
      m_clock_started = true;
      m_last_rx = now_ms;
    }

    const uint8_t result = communicate();

    if (m_timeout_ms != 0 && !m_comm_lost &&
        static_cast<uint32_t>(now_ms - m_last_rx) >= m_timeout_ms) {
      m_comm_lost = true;
      if (m_on_timeout)
        m_on_timeout();
    }

    if (m_stream_period != 0) {
      if (!m_stream_primed) {
        m_stream_primed = true;
        m_stream_next = now_ms + m_stream_period;
      } else if (static_cast<int32_t>(now_ms - m_stream_next) >= 0) {
        emit_stream_frame(now_ms);
        m_stream_next += m_stream_period;
        // Fell more than one period behind (slow loop): skip ahead instead of sending a burst.
        // The receiver sees the gap in the device time stamps.
        if (static_cast<int32_t>(now_ms - m_stream_next) >= 0)
          m_stream_next = now_ms + m_stream_period;
      }
    }

    return result;
  }

  // Legacy function for EPICS I/O Intr mode: every call without input sends all channels,
  // as fast as it is called. Prefer service() with a stream period, which is rate limited
  // and adds a sequence number and a time stamp.
  void intr_communicate()
  {
    m_io.read();
    if (m_io.m_input == nullptr)
      return;

    switch (m_io.m_input[detail::OFST_STATEMENT]) {
      case 's':
        io_intr_setter();
        return;

      case '\0':
        if (query_all() == PRC_QALL)
          m_io.write_buffer();
        return;

      default:
        return;
    }
  }

  // Returns a value to the communicate() function
  // Calls different function based on the first Byte of the input
  uint8_t process_input() {
    // Byte 0: Statement (query channel, set channel, query all channels, ...)
    // Query Byte 1: Must be 0, This is a modified version of com1 protocol is designed for EPICS
    // Query Byte 2: Must be 1, Only a single channel can be queried at a time
    // Query Byte 3: Channel Iden
    // Query Byte 4: Channel Num
    // Query Byte 5: Decimal Precision
    // Set Byte 1: Channel Iden
    // Set Byte 2: Channel Num
    // Set Byte 3+: Float formatted as string

    m_io.read();
    if (m_io.m_input == nullptr)
      return ERR_NO_DATA;

    m_io.write_debug("Processing Input: %s\n", m_io.m_input);

    switch (m_io.m_input[detail::OFST_STATEMENT]) {
      case 'q':
        return single_query();

      case 'g':
        return plain_query();

      case 's':
        return io_intr_setter();

      case 'S': {
        const uint8_t result = io_intr_setter();
        return (result == PRC_SET) ? PRC_SET_ACK : result;
      }

      case 'A':
        return query_all();

      case 'I':
        return identify();

      case 'P':
        return period_command();

      case '\0':
        return ERR_NO_DATA;

      default:
        m_io.write_debug("Unknown Query\n");
        return ERR_UNKNOWN;
    }
  }
private:
  // Bounded append helpers for building replies in the output buffer.
  // They return false, and leave the buffer NUL-terminated, when the text does not fit.
  bool put_text(size_t& pos, const char* text)
  {
    char* out = m_io.m_outbuffer;
    for (; *text != '\0'; ++text) {
      if (pos + 1 >= OutBufferSize) {
        out[pos] = '\0';
        return false;
      }
      out[pos++] = *text;
    }
    out[pos] = '\0';
    return true;
  }

  bool put_uint(size_t& pos, uint32_t value)
  {
    char digits[11];
    uint8_t n = 0;
    do {
      digits[n++] = static_cast<char>('0' + (value % 10));
      value /= 10;
    } while (value != 0);

    char text[11];
    for (uint8_t i = 0; i < n; ++i)
    { text[i] = digits[n - 1 - i]; }
    text[n] = '\0';
    return put_text(pos, text);
  }

  // Appends "<v1>:<v2>:...:<vN>" at `pos`. Returns false if it does not fit.
  bool append_values(size_t pos)
  {
    char* out = m_io.m_outbuffer;
    for (const Channel& channel : m_map.m_channels)
    {
      // Room for the longest value plus the separator / terminating NUL after it
      if (pos + detail::MAX_VALUE_CHARS >= OutBufferSize) {
        out[pos] = '\0';
        return false;
      }
      pos += detail::format_value(channel.get(), out + pos);
      out[pos++] = ':';
    }

    // Remove the last colon
    out[pos - 1] = '\0';
    return true;
  }

  // Legacy single query, kept for compatibility with LibCom1ExponentConverter.
  // The reply format has exactly one exponent digit, so values outside 1e-9 .. 9.99e9
  // (and nan / inf) cannot be represented. They used to be sent with the leading exponent
  // digit silently dropped (1.5e-12 arrived as 1.5e-2); now they are answered with ERR6.
  // New code should use "g<c><n>" instead, which has no such limit.
  uint8_t single_query() {
    char* src = m_io.m_input;

    if (!detail::has_length(src, 6))
      return ERR_SYNTAX;

    // Only a single channel can be queried at a time
    if (src[1] != '0' || src[2] != '1')
      return ERR_NUM_CHANNELS;

    // Conversions from input
    const uint8_t chnl_num = src[detail::OFST_Q_CH_NUM] - '0';
    const uint8_t precision = src[detail::OFST_Q_PRCN] - '0';

    // Floats only have enough precision for 6 decimal places
    // Negative numbers don't need to be checked b/c overflow
    if (precision > 6)
      return ERR_PRECISION_TOO_LARGE;

    m_io.write_debug("Raw Chnl Query: Chnl: %c%u, Precision: %u\n",
                     src[detail::OFST_Q_CH_IDEN],
                     chnl_num,
                     precision);

    // Search for the channel
    // Returns error if channel doesn't exist
    const auto channel = m_map.at( i16u_iden(src[detail::OFST_Q_CH_IDEN], chnl_num) );
    if (!channel)
      return channel.error();

    if (!(*channel).readable())
      return ERR_NOT_SUPPORTED;

    const float value = (*channel).get();
    if (!detail::is_finite(value))
      return ERR_VALUE;

    // Exponential str repr with <= 6 digits of precision is:
    // 1 byte for coeff sign
    // 1 byte for ones place
    // 1 byte for decimal point,
    // <= 6 bytes for precision,
    // 1 byte for E
    // 1 byte for Exponent sign,
    // 2 bytes for exponent
    // 1 byte for null terminating char
    // Exp buffer need to be at least 14 bytes (round up to 16 for evenness)
    char buffer_exp[16]{ 0 };

#if LIBCOM1_USE_DTOSTRE
    // The Arduino IDE does not have the linker flags set to
    // enable vfprintf with float support on the AVR8 platform
    dtostre(value, buffer_exp, precision, DTOSTR_ALWAYS_SIGN | DTOSTR_PLUS_SIGN);
#elif defined(__AVR__)
    // avr-libc does not support '*' (variable width precision). This is an ugly workaround
    char conv_sci_notation[] = "%+.0e";
    conv_sci_notation[3] = src[detail::OFST_Q_PRCN];
    snprintf(buffer_exp, 16, conv_sci_notation, static_cast<double>(value));
#else
    // This is the version as outlined by the C/C++ standard in the header <cstdio> / <stdio.h>
    snprintf(buffer_exp, 16, "%+.*e", precision, static_cast<double>(value));
#endif
    m_io.write_debug("As sci. notation: %s\n", buffer_exp);

    // Locate the exponent and make sure it is a single digit
    const char* e_ptr = strchr(buffer_exp, 'e');
    if (e_ptr == nullptr)
      e_ptr = strchr(buffer_exp, 'E');
    if (e_ptr == nullptr || (e_ptr[1] != '+' && e_ptr[1] != '-') || e_ptr[2] == '\0')
      return ERR_VALUE;

    uint8_t exponent = 0;
    const char* digit = e_ptr + 2;
    for (; *digit >= '0' && *digit <= '9'; ++digit) {
      if (exponent > 9)
        return ERR_VALUE;
      exponent = static_cast<uint8_t>(exponent * 10 + (*digit - '0'));
    }
    if (*digit != '\0' || exponent > 9)
      return ERR_VALUE;

    // Convert sci notation to original libcom1 format and write to out buffer
    // Ex: +1.56e+02 -> +1562+     +3e-01 -> +31-
    char* out = m_io.m_outbuffer;
    memset(out, 0, OutBufferSize);
    size_t pos = 0;
    out[pos++] = 'o';
    out[pos++] = src[detail::OFST_Q_CH_IDEN];
    out[pos++] = src[detail::OFST_Q_CH_NUM];

    // Coefficient sign and digits, without the decimal point (at most 8 characters)
    for (const char* c = buffer_exp; c != e_ptr; ++c) {
      if (*c != '.')
        out[pos++] = *c;
    }
    out[pos++] = static_cast<char>('0' + exponent); // Exp
    out[pos++] = e_ptr[1];                          // Exp Sign
    out[pos] = '\0';

    m_io.write_debug("As formatted: %s\n", m_io.m_outbuffer);

    return PRC_QUERY;
  }

  // Single query in the same plain format as query-all: "g<c><n>" -> "o<value>".
  // Parses with a stock StreamDevice (`in "o%g";`), no custom converter needed.
  uint8_t plain_query() {
    char* src = m_io.m_input;

    if (!detail::has_length(src, 3))
      return ERR_SYNTAX;

    const uint8_t chnl_num = src[2] - '0';
    const auto channel = m_map.at( i16u_iden(src[1], chnl_num) );
    if (!channel)
      return channel.error();

    if (!(*channel).readable())
      return ERR_NOT_SUPPORTED;

    char* out = m_io.m_outbuffer;
    memset(out, 0, OutBufferSize);
    out[0] = 'o';
    detail::format_value((*channel).get(), out + 1);

    return PRC_GET;
  }

  // Returns specific error if the command is malformed or the channel does not exist
  // If there is no error, sets the given channel to the given new value and returns PRC_SET
  // Includes debug output
  uint8_t io_intr_setter() {
    char* src = m_io.m_input;

    // There has to be a channel and at least one character of value
    if (!detail::has_length(src, 4))
      return ERR_SYNTAX;

    // Conversions from input
    const uint8_t chnl_num = src[detail::OFST_S_CH_NUM] - '0';

    // The whole rest of the line has to be one finite number. atof() used to turn
    // garbage into a setpoint of 0 and accept trailing junk.
    char* value_start = &src[detail::OFST_S_FLT];
    char* value_end = value_start;
    const float setval = static_cast<float>(strtod(value_start, &value_end));
    if (value_end == value_start)
      return ERR_SYNTAX;
    while (*value_end == ' ' || *value_end == '\t' || *value_end == '\r')
    { ++value_end; }
    if (*value_end != '\0' || !detail::is_finite(setval))
      return ERR_SYNTAX;

    m_io.write_debug("Raw Channel Set: Chnl: %c%u, Setval: %f\n",
                     src[detail::OFST_S_CH_IDEN],
                     chnl_num,
                     static_cast<double>(setval));

    // Search for channel
    const auto channel = m_map.at(  i16u_iden( src[detail::OFST_S_CH_IDEN], chnl_num) );
    if (!channel)
      return channel.error();

    if (!(*channel).writable())
      return ERR_NOT_SUPPORTED;

    // Call the setter
    (*channel).set(setval);

    return PRC_SET;
  }

  // Outputs all channels and their values, then returns PRC_QALL
  // The values are in %g form, separated by ':'. On Arduino AVR, which has no float printf,
  // they are in %e form with the trailing zeros removed.
  uint8_t query_all() {
    m_io.write_debug("Query All\n");

    char* out = m_io.m_outbuffer;
    memset(out, 0, OutBufferSize);
    out[0] = 'o';
    if (!append_values(1))
      return ERR_BUFFER;

    m_io.write_debug("Query All: %s\n", m_io.m_outbuffer);
    return PRC_QALL;
  }

  // "I" -> oID=<name>;FW=<version>;PROTO=<n>;CH=<c1n1>,<c2n2>,...
  // Lets the control system check that the device on this port is the one it expects,
  // with the firmware and channel order the database was written for.
  uint8_t identify() {
    char* out = m_io.m_outbuffer;
    memset(out, 0, OutBufferSize);
    size_t pos = 0;

    bool ok = put_text(pos, "oID=") && put_text(pos, m_name) &&
              put_text(pos, ";FW=") && put_text(pos, m_version) &&
              put_text(pos, ";PROTO=") && put_uint(pos, PROTOCOL_VERSION) &&
              put_text(pos, ";CH=");

    bool first = true;
    for (const Channel& channel : m_map.m_channels)
    {
      if (!ok)
        break;
      const char iden[2] = { channel.m_idenA, '\0' };
      ok = (first || put_text(pos, ",")) && put_text(pos, iden) && put_uint(pos, channel.m_idenB);
      first = false;
    }

    return ok ? PRC_IDENT : ERR_BUFFER;
  }

  // "P<ms>" -> ok. Sets the stream period, 0 switches streaming off.
  uint8_t period_command() {
    char* src = m_io.m_input;

    if (src[1] < '0' || src[1] > '9')
      return ERR_SYNTAX;

    char* value_end = &src[1];
    const unsigned long period = strtoul(&src[1], &value_end, 10);
    while (*value_end == ' ' || *value_end == '\t' || *value_end == '\r')
    { ++value_end; }
    if (*value_end != '\0')
      return ERR_SYNTAX;

    return set_stream_period(static_cast<uint32_t>(period)) ? PRC_PERIOD : ERR_BUFFER;
  }

  // t<seq>:<device ms>:<v1>:...:<vN>
  // seq counts frames (wraps at 65535) so the receiver can detect lost ones;
  // the device time gives the sampling instant independent of transport delays.
  void emit_stream_frame(uint32_t now_ms) {
    char* out = m_io.m_outbuffer;
    memset(out, 0, OutBufferSize);
    size_t pos = 0;

    const bool ok = put_text(pos, "t") && put_uint(pos, m_seq) && put_text(pos, ":") &&
                    put_uint(pos, now_ms) && put_text(pos, ":") && append_values(pos);
    ++m_seq;
    if (ok)
      m_io.write_buffer();
  }
};

} // namespace com1

} // namespace mist1

// Serial setup macro
#if defined(Arduino_h) && defined(__AVR__)

#define PRINTF_SERIAL_PREINIT() \
  static FILE mystdout;                                                   \
  int put_char(char data, FILE* stream) { Serial.print(data); return 0; } \

#define PRINTF_SERIAL_INIT() \
  fdev_setup_stream(&mystdout, put_char, NULL, _FDEV_SETUP_WRITE);        \
  stdout = &mystdout;                                                     \

#else
#define PRINTF_SERIAL_PREINIT()
#define PRINTF_SERIAL_INIT()
#endif // Arduino_h and __AVR__ defined for serial setup macro

#endif // e53ab5d5_libcom1_eval_h
