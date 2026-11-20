#ifndef libcom1_tests_dtostre_shim_h
#define libcom1_tests_dtostre_shim_h

// Stand-in for avr-libc's dtostre() so the Arduino AVR formatting code path of libcom1
// (LIBCOM1_USE_DTOSTRE=1) can be compiled and tested on a PC.
// `make avr-sim` checks this stand-in against the real avr-libc function on a simulated ATmega2560.

#include <stdio.h>

#define DTOSTR_ALWAYS_SIGN 0x01
#define DTOSTR_PLUS_SIGN   0x02
#define DTOSTR_UPPERCASE   0x04

inline char* dtostre(double val, char* s, unsigned char prec, unsigned char flags)
{
  if (prec > 7)
    prec = 7;
  const char* fmt = (flags & DTOSTR_PLUS_SIGN) ? "%+.*e"
                  : (flags & DTOSTR_ALWAYS_SIGN) ? "% .*e"
                  : "%.*e";
  sprintf(s, fmt, static_cast<int>(prec), val);
  return s;
}

#endif // libcom1_tests_dtostre_shim_h
