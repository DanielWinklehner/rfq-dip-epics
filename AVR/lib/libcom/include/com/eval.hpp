#ifndef COM_EVAL_HPP
#define COM_EVAL_HPP

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "com/com.hpp"

namespace Comm {

#if USE_LIBCOM == 1
template<size_t N1, size_t N3>
int
conv_sci_to_libcom1_out(char (&src)[N1],
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
  if (precision == 0) {
    // Ex: +3e-01 -> +31-
    // Skip the decimal pt
    target[2 + 1 - 1] = src[2 + 4 - 1]; // Exp
    target[2 + 2 - 1] = src[2 + 2 - 1]; // Exp Sign
  } else {
    // Ex: +1.56E+02 -> +1562+
    target[2 + precision + 1 - 1] = src[3 + precision + 4 - 1]; // Exp
    target[2 + precision + 2 - 1] = src[3 + precision + 2 - 1]; // Exp Sign
  }
  *bytes_written = 2 + precision + 2;

  return 0;
}

template<size_t N1, size_t N3>
uint8_t
io_intr_query(const ChannelMap<N1>& channels, char (&write_buffer)[N3]) {
  DEBUG_PRINT("Query All\n");
  // Get all values in %g form.
  memset(write_buffer, 0, N3);
  write_buffer[0] = 'o';
  int bytes_written = 1;
  for (size_t i = 0; i < channels.size(); ++i) {
    bytes_written += snprintf(write_buffer + bytes_written,
                              N3 - bytes_written,
                              "%g:",
                              (channels[i].getter)());
    DEBUG_PRINT("Total Bytes Written: %d\n", bytes_written);
  }
  write_buffer[bytes_written - 1] = '\0'; // Remove last colon
  DEBUG_PRINT("Query All: %s\n", write_buffer);
  return PRC_QALL;
}

template<size_t N1, size_t N2>
uint8_t
io_intr_setter(const ChannelMap<N1>& channels, char (&src)[N2]) {
  // Conversions first
  uint8_t num = src[detail::OFST_S_CH_NUM] - '0';
  float setval = atof(&src[detail::OFST_S_FLT]);

  DEBUG_PRINT("Raw Query: Ch_iden: %hhu, Ch_num: %hhu, Setval: %f\n",
              src[detail::OFST_S_CH_IDEN],
              num,
              setval);

  // Find the channel
  uint8_t channel_lookup_error;
  const Channel& channel =
    channels.at(src[detail::OFST_S_CH_IDEN], num, &channel_lookup_error);
  if ((bool)channel_lookup_error)
    return ERR_CHANNEL_LOOKUP;

  DEBUG_PRINT("Query: Ch_iden: %c,  Ch_num: %hhu, Setval: %f\n",
              channel.iden,
              channel.num,
              setval);

  // Call the channel setter
  (*channel.setter)(setval);
  return PRC_SET;
}

template<size_t N1, size_t N2, size_t N3>
uint8_t
eval(const ChannelMap<N1>& channels, char (&src)[N2], char (&write_buffer)[N3])
{
  // Byte 0: Statement
  // Query Byte 1: Must be 0, This is a modified version of com1 protocol is designed for EPICS
  // Query Byte 2: Must be 1, Only a single channel can be queried at a time
  // Query Byte 3: Channel Iden
  // Query Byte 4: Channel Num
  // Query Byte 5: Decimal Precision
  // Set Byte 1: Channel Iden
  // Set Byte 2: Channel Num
  // Set Byte 3+: Float formatted as string

  if (src[detail::OFST_STATEMNT] == 'q') {
    // Conversions first
    uint8_t num = src[detail::OFST_Q_CH_NUM] - '0';
    uint8_t precision = atoi(&src[detail::OFST_Q_PRCN]);

    DEBUG_PRINT("Raw Query: Ch_iden: %hhu,  Ch_num: %hhu, Precision: %hhu\n",
                src[detail::OFST_Q_CH_IDEN],
                num,
                precision);

    // Search the the channel
    uint8_t channel_lookup_error;
    const Channel& channel =
      channels.at(src[detail::OFST_Q_CH_IDEN], num, &channel_lookup_error);
    if ((bool)channel_lookup_error)
      return ERR_CHANNEL_LOOKUP;

    DEBUG_PRINT("Query: Ch_iden: %c,  Ch_num: %hhu, Precision: %hhu\n",
                channel.iden,
                channel.num,
                precision);

    // Floats only have enough precision for 6 decimal places
    if (precision > 6) {
      return ERR_PRECISION_TOO_LARGE;
    }

    // Exponential str repr with 6 digits of precision is:
    // 1 byte for coeff sign
    // 1 byte for ones place
    // 1 byte for decimal point,
    // <precision> bytes for precision,
    // 1 byte for E
    // 1 byte for Exponent sign,
    // 2 bytes for exponent
    // 1 byte for null term
    // Exp buffer need to be at least 14 bytes (6 digits of precision)

    // Conv buffer needs: <buffer_exp> bytes
    // - 1 for the deciaml pt
    // - 1 for the E
    // - 1 for the second exp. digit
    // Conv buffer needs at least 11 bytes (6 digits of precision)

    // It is easiest just to allocate 16 bytes
    char buffer_exp[16]{ 0 };
    char buffer_conv[16]{ 0 };

    // avr-libc does not support the * (variable width precision)
    // this is an ugly workaround
    char conv_sci_notation[] = "%+.0e";
    conv_sci_notation[3] = src[detail::OFST_Q_PRCN];

    snprintf(buffer_exp, N3, conv_sci_notation, (*channel.getter)());

    DEBUG_PRINT("Conv to Exp Buffer: %s\n", buffer_exp);

    // Convert to libcom1 format
    uint8_t conv_bytes_wrote;
    conv_sci_to_libcom1_out(
      buffer_exp, precision, buffer_conv, &conv_bytes_wrote);

    DEBUG_PRINT("Conv to libcom1 Buffer: %s, Bytes Written: %hhu\n",
                buffer_conv,
                conv_bytes_wrote);

    // Write to the out buffer
    memset(write_buffer, 0, N3);
    write_buffer[0] = 'o';
    write_buffer[1] = src[detail::OFST_Q_CH_IDEN];
    write_buffer[2] = src[detail::OFST_Q_CH_NUM];
    memcpy(write_buffer + 3, buffer_conv, conv_bytes_wrote);

    DEBUG_PRINT("Output Buffer: %s\n", write_buffer);
    return PRC_QUERY;

  } else if (src[detail::OFST_STATEMNT] == 's') {
    return io_intr_setter(channels, src);

  } else if (src[detail::OFST_STATEMNT] == 'A') {
    return io_intr_query(channels, write_buffer);
  } else {

  }

  return ERR_UNKNOWN;
}

#endif // USE_LIBCOM == 1

#if USE_LIBCOM == 2

#endif //USE_LIBCOM == 2

} // namespace Comm
#endif // EVAL_HPP
