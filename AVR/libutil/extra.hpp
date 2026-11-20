#ifndef d4c36745_libutil_extra_h
#define d4c36745_libutil_extra_h

// Needed on every platform, not only AVR: abort(), ::size_t and ::ptrdiff_t are used below.
#include <stdlib.h>
#include <stddef.h>

namespace stdx
{
  // inline: this header may be included from more than one translation unit
  [[noreturn]] inline void terminate() {
    abort();
  }

  using ptrdiff_t = ::ptrdiff_t;
  using size_t = ::size_t;

  // Not sure if needed
  using nullptr_t = decltype(nullptr);
}


#endif // d4c36745_libutil_extra_h
