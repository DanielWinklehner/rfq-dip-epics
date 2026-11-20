/**
 * LibCom1ExponentConverter.cc
 *
 * ONLY NEEDED FOR THE LEGACY SINGLE QUERY ("q01...", com1_getLink in libcom1.proto).
 * Everything else in libcom1.proto, including the single query "g..." (com1_get), uses plain
 * %g numbers and works with an unmodified StreamDevice. New databases do not need this file.
 *
 * IMPORTANT (if you do want it):
 * - Place me in <StreamDeviceRoot>/src
 * - Don't forget to modify <StreamDeviceRoot>/src/CONFIG_STREAM and add me
 *
 * This file provides the conversion from libcom1's legacy float string format to a double:
 *
 *   <sign><digits><exponent digit><exponent sign>      the first digit is the ones place
 *
 *   "+40923+"  ->  +4.092e+3
 *   "+15007-"  ->  +1.500e-7
 *   "+31-"     ->  +3e-1
 *
 * The format has a single exponent digit, so it covers 1e-9 to 9.99e9 only. Devices answer
 * ERR6 for values outside that range (older firmware silently dropped the first exponent
 * digit, 1.5e-12 arrived as 1.5e-2).
 *
 * Author(s): Ryan Yang (ryang2@mit.edu)
 * Changlog:
 * 2026/11/20 - Reject malformed input instead of reading and writing outside the buffer
 *              (replies shorter than 2 characters), accept a trailing CR, convert in double
 *              precision
 * 2021/05/23 - Documentation
 * 2020/11/01 - Added file
 *
 */

#include "StreamFormatConverter.h"
#include "StreamError.h"
#include <math.h>
#include <string.h>

class LibCom1ExponentConverter : public StreamFormatConverter
{
    virtual int parse(const StreamFormat&, StreamBuffer&, const char*&, bool);
    virtual ssize_t scanDouble(const StreamFormat&, const char*, double&);
//    virtual bool printDouble(const StreamFormat&, StreamBuffer&, double);
};

int LibCom1ExponentConverter::
parse(const StreamFormat&, StreamBuffer&,
    const char*&, bool)
{
    return double_format;
}

ssize_t LibCom1ExponentConverter::
scanDouble(const StreamFormat& fmt, const char* input, double& value)
{
    const size_t available = strlen(input);
    const size_t consumed = (fmt.width > 0 && fmt.width < available) ? fmt.width : available;

    // Serial.println() ends a line with CR LF while the protocol terminator is LF, so a CR
    // (or blanks) can still be attached to the number. It is consumed but not parsed.
    size_t nbytes = consumed;
    while (nbytes > 0 &&
           (input[nbytes - 1] == '\r' || input[nbytes - 1] == ' ' || input[nbytes - 1] == '\t'))
        nbytes--;

    // Shortest valid text: sign, one digit, exponent digit, exponent sign.
    // A float has at most 9 significant digits.
    const size_t max_digits = 9;
    if (nbytes < 4 || nbytes > 3 + max_digits)
        return -1;

    const char mantissa_sign = input[0];
    const char exponent_digit = input[nbytes - 2];
    const char exponent_sign = input[nbytes - 1];
    if ((mantissa_sign != '+' && mantissa_sign != '-') ||
        (exponent_sign != '+' && exponent_sign != '-') ||
        exponent_digit < '0' || exponent_digit > '9')
        return -1;

    // The digits between the sign and the exponent, as an integer
    double mantissa = 0.0;
    int digits = 0;
    for (size_t i = 1; i < nbytes - 2; i++) {
        if (input[i] < '0' || input[i] > '9')
            return -1;
        mantissa = mantissa * 10.0 + (input[i] - '0');
        digits++;
    }

    // The first digit is the ones place: value = mantissa * 10^(exponent - (digits - 1)).
    // Scaling by an exact power of ten in one step keeps the result correctly rounded.
    int exponent = exponent_digit - '0';
    if (exponent_sign == '-')
        exponent = -exponent;
    exponent -= digits - 1;

    double result = (exponent >= 0) ? mantissa * pow(10.0, exponent)
                                    : mantissa / pow(10.0, -exponent);
    if (mantissa_sign == '-')
        result = -result;

    debug("LIBCOM1EXP input=\"%s\" used=%d val=%g\n", input, (int)nbytes, result);

    if (fmt.flags & skip_flag) return consumed;
    value = result;
    return consumed;
}

RegisterConverter (LibCom1ExponentConverter, "z");
