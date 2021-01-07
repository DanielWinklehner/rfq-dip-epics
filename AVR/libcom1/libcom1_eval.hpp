#ifndef e53ab5d5_libcom1_eval_h
#define e53ab5d5_libcom1_eval_h

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "libcom1_com.hpp"

namespace mist1 {

namespace com1 {

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
    : m_infunc(in), m_outfunc(out)
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

template<size_t OutBufferSize, size_t ChannelMapSize>
class SerialDevice{
public:
  IOHandler<OutBufferSize>& m_io;
  const ChannelMap<ChannelMapSize>& m_map;
public:
  SerialDevice(IOHandler<OutBufferSize>& io, const ChannelMap<ChannelMapSize>& channels)
    : m_io(io), m_map(channels)
  {}

  // Function for the device to process the input and write an output.
  // Unacceptable inputs will output an error, elaborated in the README.
  // This function would be continuously run in a loop. If there's no input, there is no output.
  void communicate()
  {
    switch (process_input()) {
      case PRC_QUERY:
      case PRC_QALL:
        m_io.write_buffer();
        break;

      case ERR_PRECISION_TOO_LARGE:
        m_io.write("ERR1");
        break;

      case ERR_CHANNEL_LOOKUP:
        m_io.write("ERR4");
        break;

      case ERR_UNKNOWN:
        m_io.write("ERR0");
        break;

      case ERR_NO_DATA:
      case PRC_SET:
      default:
        break;
    }
  }

  // Function for polling communication.
  // Null input would query all channels.
  void intr_communicate()
  {
    m_io.read();
    switch (m_io.m_input[detail::OFST_STATEMENT]) {
      case 's':
        io_intr_setter();
        return;

      case '\0':
        query_all();
        m_io.write_buffer();
        return;

      default:
        return;
    }
  }

  // Returns a value to the communicate() function
  // Calls different function based on the first Byte of the input (query channel, set channel, or query all channels)
  uint8_t process_input() {
    // Byte 0: Statement (query channel, set channel, query all channels)
    // Query Byte 1: Must be 0, This is a modified version of com1 protocol is designed for EPICS
    // Query Byte 2: Must be 1, Only a single channel can be queried at a time
    // Query Byte 3: Channel Iden
    // Query Byte 4: Channel Num
    // Query Byte 5: Decimal Precision
    // Set Byte 1: Channel Iden
    // Set Byte 2: Channel Num
    // Set Byte 3+: Float formatted as string

    m_io.read();
    m_io.write_debug("Processing Input: %s\n", m_io.m_input);

    switch (m_io.m_input[detail::OFST_STATEMENT]) {
      case 'q':
        return single_query();

      case 's':
        return io_intr_setter();

      case 'A':
        return query_all();

      case '\0':
        return ERR_NO_DATA;

      default:
        m_io.write_debug("Unknown Query\n");
        return ERR_UNKNOWN;
    }
  }
private:
  // Returns specific error if the precision is too large or the channel does not exist
  // If there is no error, outputs the queried channel's information to the indicated precision and returns PRC_QUERY
  // Includes debug output.
  uint8_t single_query() {
    char* src = m_io.m_input;

    // Conversions from input
    uint8_t chnl_num = src[detail::OFST_Q_CH_NUM] - '0';
    uint8_t precision = atoi(&src[detail::OFST_Q_PRCN]);

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
//      return ERR_CHANNEL_LOOKUP;

    m_io.write_debug("Processed Query: Chnl: %c%u, Precision: %u\n",
                     (*channel).m_idenA,
                     (*channel).m_idenB,
                     precision);

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

    // The Arduino IDE does not have the linker flags set to
    // enable vfprintf with float support on the AVR8 platform
#if defined(Arduino_h) && defined(__AVR__)
    dtostre( (*channel).m_getter() , buffer_exp, precision, DTOSTR_ALWAYS_SIGN | DTOSTR_PLUS_SIGN);
#else
    // This is the version as outlined by the C/C++ standard in the header <cstdio> / <stdio.h>
    snprintf(buffer_exp, 16, "%+.*e", precision, (*channel).m_getter());
#endif
    m_io.write_debug("As sci. notation: %s\n", buffer_exp);

//   Original:
//    // Note: avr-libc does not support '*' (variable width precision)
//    // this is an ugly hack / workaround
//    char conv_sci_notation[] = "%+.0e";
//    conv_sci_notation[3] = src[detail::OFST_Q_PRCN];

//    // Convert the getter value to sci notation
//    snprintf(buffer_exp, 16, conv_sci_notation, (*channel).m_getter());

    // Convert sci notation to original libcom1 format
    // and write to out buffer
    memset(m_io.m_outbuffer, 0, OutBufferSize);
    m_io.m_outbuffer[0] = 'o';
    m_io.m_outbuffer[1] = src[detail::OFST_Q_CH_IDEN];
    m_io.m_outbuffer[2] = src[detail::OFST_Q_CH_NUM];

    char* target = m_io.m_outbuffer + 3;
    // Conv: Coefficient Sign + Ones place always present
    memcpy(target, buffer_exp, 2);
    // Conv: Writer from just after the decimal, up to `precision` bytes
    memcpy(target + 2, buffer_exp + 3, precision);
    // Conv: Write the exponent (assuming it be a single digit) and exponent sign
    if (precision == 0)
    {
      // Ex: +3e-01 -> +31- , Skips the decimal pt
      target[2 + 1 - 1] = buffer_exp[2 + 4 - 1]; // Exp
      target[2 + 2 - 1] = buffer_exp[2 + 2 - 1]; // Exp Sign
    } else {
      // Ex: +1.56E+02 -> +1562+
      target[2 + precision + 1 - 1] = buffer_exp[3 + precision + 4 - 1]; // Exp
      target[2 + precision + 2 - 1] = buffer_exp[3 + precision + 2 - 1]; // Exp Sign
    }

    m_io.write_debug("As formatted: %s\n", m_io.m_outbuffer);

    return PRC_QUERY;
  }

  // Returns specific error if the channel does not exist
  // If there is no error, sets the given channel to the given new value and returns PRC_QUERY
  // Includes debug output
  uint8_t io_intr_setter() {
    char* src = m_io.m_input;

    // Conversions from input
    uint8_t chnl_num = src[detail::OFST_S_CH_NUM] - '0';
    float setval = atof(&src[detail::OFST_S_FLT]);

    m_io.write_debug("Raw Channel Set: Chnl: %c%u, Setval: %f\n",
                     src[detail::OFST_S_CH_IDEN],
                     chnl_num,
                     setval);

    // Search for channel
    const auto channel = m_map.at(  i16u_iden( src[detail::OFST_S_CH_IDEN], chnl_num) );
    if (!channel)
      return channel.error();
//    if ((bool) channel_lookup_error)
//      return ERR_CHANNEL_LOOKUP;

    m_io.write_debug("Processed Query: Chnl: %c%u, Setval: %f\n",
                     (*channel).m_idenA,
                     (*channel).m_idenB,
                     setval);

    // Call the setter
    (*channel).m_setter(setval);

    return PRC_SET;
  }

  // Outputs all channels and their values, then returns PRC_QALL
  // Includes debug output
  uint8_t query_all() {
  m_io.write_debug("Query All\n");

    // Get all values in %g form, separated by ':'
    char* target = m_io.m_outbuffer;
    memset(target, 0, OutBufferSize);
    target[0] = 'o';
    int bytes_written = 1;
    for (const Channel& channel : m_map.m_channels)
    {
      // The Arduino IDE does not support for any float-related printf's, so
      // we opt to use %e, with trailing zeros removed.
#if defined(Arduino_h) && defined(__AVR__)
      dtostre( channel.m_getter() , target + bytes_written, 6, DTOSTR_ALWAYS_SIGN | DTOSTR_PLUS_SIGN);

      // Trailing zeros are removed from the fractional part of the result
      char* e_ptr = target + bytes_written + 9;

      char* zero_start = e_ptr;
      while(zero_start != target + bytes_written + 3 && *(zero_start - 1) == '0')
      { --zero_start; }

      m_io.write_debug("Outbuffer: %s\n", target);

      // 1 for e, 1 for sign, 2 for power
      memmove(zero_start, e_ptr, 4);

      bytes_written += (13 - (e_ptr - zero_start));

      // Add colon to end
      target[bytes_written++] = ':';
#else
      bytes_written += snprintf(target + bytes_written,
                                OutBufferSize - bytes_written,
                                "%g:",
                                static_cast<double>( channel.m_getter() ));
#endif
      m_io.write_debug("Total Bytes Written: %i\n", bytes_written);
    }

    // Remove the last colon
    target[bytes_written - 1] = '\0';
    m_io.write_debug("Query All: %s\n", m_io.m_outbuffer);
    return PRC_QALL;
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
