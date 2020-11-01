// Place me in StreaDevice/src
// Don't forget to modify StreamDevice/src/CONFIG_STREAM 

#include "StreamFormatConverter.h"
#include "StreamError.h"
#include <math.h>

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
    float mantissa;
    int exponent;
    int length = -1;

    size_t nbytes = fmt.width > 0 ? fmt.width : strlen(input);
    char new_input[256]{0};
    memcpy(new_input, input, nbytes);

    // Swap last two bytes and add back decimal
    char tmp = new_input[nbytes - 2];
    new_input[nbytes - 2] = new_input[nbytes - 1];
    new_input[nbytes - 1] = tmp;

    // Place decimal pt
    char* ptr = new_input + 2;            // pointer to where . would be
    memmove(ptr + 1, ptr, strlen(ptr) + 1);  // +1 for the trailing null
    *ptr = '.';

    sscanf(new_input, "%f%d%n", &mantissa, &exponent, &length);

    debug("LIBCOM1EXP original_input= \"%s\" new_input=\"%s\" mantissa=\"%f\" exp=\"%d\" val=\"%f\" len=\"%d\"\n", input, new_input, mantissa, exponent, (double)(mantissa) * pow(10.0, exponent) , length);

    length -= 1; // bc of the decimal we placed
    if (fmt.flags & skip_flag) return length;
    if (length == -1) return -1;
    value = (double)(mantissa) * pow(10.0, exponent);
    return length;
}

RegisterConverter (LibCom1ExponentConverter, "z");

