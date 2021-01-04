#ifndef d4c36745_libutil_extra_h
#define d4c36745_libutil_extra_h

#ifdef __AVR__
#include <stdlib.h>
#include <stddef.h>
#endif

namespace stdx
{
  [[noreturn]] void terminate() {
    abort();
  }

  using ptrdiff_t = ::ptrdiff_t;
  using size_t = ::size_t;

  // Not sure if needed
  using nullptr_t = decltype(nullptr);
}


#endif // d4c36745_libutil_extra_h
