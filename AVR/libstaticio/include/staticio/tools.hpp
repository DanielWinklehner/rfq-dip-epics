#ifndef TOOLS_HPP
#define TOOLS_HPP

#include <stdlib.h>
#include <stdio.h>

namespace IO {

template <typename T>
void progmem_read (const T * sce, T& dest)
{
  memcpy_P (&dest, sce, sizeof (T));
}

template <typename T>
T progmem_get (const T * sce)
{
  static T temp;
  memcpy_P (&temp, sce, sizeof (T));
  return temp;
}

template< typename T, size_t N >
size_t ArraySize (T (&) [N])
{
  return N;
}


} //namespace IO

#endif // TOOLS_HPP
