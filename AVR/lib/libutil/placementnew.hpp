#ifndef d4c36745_libutil_pnew_h
#define d4c36745_libutil_pnew_h

#include <stdlib.h>

#ifdef __AVR__
// Placement new operators
void* operator new( size_t, void* ptr )
{ 
  return ptr;
}

 void* operator new[]( size_t, void* ptr )
{
  return ptr; 
}
#endif

#endif // d4c36745_libutil_pnew_h
