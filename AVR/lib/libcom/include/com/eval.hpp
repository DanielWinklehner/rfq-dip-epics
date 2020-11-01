#ifndef COM_EVAL_HPP
#define COM_EVAL_HPP

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

namespace Eval {

//typedef void (*read_func)();
//typedef void (*set_func)(int);

#if USE_LIBCOM == 1
static constexpr uint8_t ERR_CHANNEL_LOOKUP = 10;
static constexpr uint8_t ERR_PRECISION_TOO_LARGE = 11;

template<size_t N1, size_t N3>
int conv_sci_to_libcom1_out(char (&src)[N1],
                            uint8_t precision,
                            char (&target)[N3],
                            uint8_t* bytes_written)
{
  *bytes_written = 0;
  // Coefficient Sign + Ones place always present
  memcpy(target, src, 2);

  // Write from just after the decimal, up to precision bytes.
  memcpy(target + 2, src + 3, precision);

  // Write the exponent (assuming it to be a single digit) and exponent sign
  if (precision == 0)  {
      // Ex: +3e-01 -> +31-
    target[2 + 1 - 1] = src[2 + 4 - 1]; // no decimal pt
    target[2 + 2 - 1] = src[2 + 2 - 1];         // no decimal pt
  }
  else {
      // Ex: +1.56E+02 -> +1562+
    target[2 + precision + 1 - 1] = src[3 + precision + 4 - 1];
    target[2 + precision + 2 - 1] = src[3 + precision + 2 - 1];
  }
  *bytes_written = 2+precision+2;

  return 0;
}

using GetterFunc = float (*)();
using SetterFunc = void (*)(float);

struct Channel {
    char iden;
    uint8_t num;
    GetterFunc getter;
    SetterFunc setter;
};

template <size_t N>
struct ChannelMap {
  Channel channels[N];

  constexpr const Channel& at(const char& iden, const uint8_t& num, uint8_t* error) const {
    *error=1;
    for (const auto& channel: channels)
    {
        DEBUG_PRINT("Checking: %c %hhu\n", channel.iden, channel.num);
        if (channel.iden == iden && channel.num == num) {
            *error=0;
            return channel;
          }
    }
    return channels[0];
  }

  constexpr size_t size() const {
    return N;
  }
};

template<typename T, size_t N>
constexpr size_t arraysize(T(&)[N]) {
    return N;
}


template<size_t N1, size_t N2, size_t N3>
uint8_t
eval(const ChannelMap<N1>& channels, char (&src)[N2], char (&write_buffer)[N3]) {
  // Byte 0: Statement
  // Query Byte 1: Must be 0, This is a modified version of com1 protocol is designed for EPICS
  // Query Byte 2: Must be 1, Only a single channel can be queried at a time
  // Query Byte 3: Channel Iden
  // Query Byte 4: Channel Num
  // Query Byte 5: Decimal Precision
  // Set Byte 1: Channel Iden
  // Set Byte 2: Channel Num
  // Set Byte 3+: Float formatted as string

  if (src[0] == 'q') {
    uint8_t num = src[4] - '0';
    uint8_t precision = atoi(&src[5]);

    DEBUG_PRINT("Raw Query: Ch_iden: %hhu,  Ch_num: %hhu, Precision: %hhu\n", src[3], num, precision);

    uint8_t channel_lookup_error;
    const Channel& channel = channels.at(src[3], num, &channel_lookup_error);
    if ((bool)channel_lookup_error)
      return ERR_CHANNEL_LOOKUP;

    DEBUG_PRINT("Query: Ch_iden: %c,  Ch_num: %hhu, Precision: %hhu\n", channel.iden, channel.num, precision);

    if (precision > 6) {
        return ERR_PRECISION_TOO_LARGE;
    } // Floats only have enough precision for 6 decimal places

    // Exponential str repr with 6 digits of precision is:
    // 1 byte for coeff sign, 1 byte for ones place
    // 1 byte for decimal point, 6 bytes for precision, 1 byte for E
    // 1 byte for Exponent sign, 2 bytes for exponent, 1 byte for null term
    char buffer_exp[N3]{0};
    char buffer_conv[N3]{0};

    switch (precision) {
      case 0:
        snprintf(buffer_exp, N3, "%+.0e", (*channel.getter)());
        break;
      case 1:
        snprintf(buffer_exp, N3, "%+.1e", (*channel.getter)());
        break;
      case 2:
        snprintf(buffer_exp, N3, "%+.2e", (*channel.getter)());
        break;
      case 3:
        snprintf(buffer_exp, N3, "%+.3e", (*channel.getter)());
        break;
      case 4:
        snprintf(buffer_exp, N3, "%+.4e", (*channel.getter)());
        break;
      case 5:
        snprintf(buffer_exp, N3, "%+.5e", (*channel.getter)());
        break;
      case 6:
        snprintf(buffer_exp, N3, "%+.6e", (*channel.getter)());
        break;
      default:
        //error
        break;
    }

    DEBUG_PRINT("Conv to Exp Buffer: %s\n", buffer_exp);

    uint8_t conv_bytes_wrote;
    conv_sci_to_libcom1_out(buffer_exp,
                            precision,
                            buffer_conv,
                            &conv_bytes_wrote);

    DEBUG_PRINT("Conv to libcom1 Buffer: %s, Bytes Written: %hhu\n", buffer_conv, conv_bytes_wrote);

    memset(write_buffer, 0, N3);
    write_buffer[0] = 'o';
    write_buffer[1] = src[3]; // Channel Iden
    write_buffer[2] = src[4]; // Chanel NUm
    memcpy(write_buffer + 3, buffer_conv, conv_bytes_wrote);

    DEBUG_PRINT("Output Buffer: %s\n", write_buffer);
    return 0;
  }
  else if (src[0] == 's') {
    uint8_t num = src[2] - '0';
    float setval = atof(&src[3]);

    uint8_t channel_lookup_error;
    const Channel& channel = channels.at(src[1], num, &channel_lookup_error);
    if ((bool)channel_lookup_error)
      return ERR_CHANNEL_LOOKUP;

    (*channel.setter)(setval);
    return 0;
  }
  else {

  }

  return 0;
}
#endif

#if USE_LIBCOM == 2

#endif



} // namespace Eval
#endif // EVAL_HPP
