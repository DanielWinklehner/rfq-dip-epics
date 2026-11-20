// Runs tests/script.hpp on the PC and prints every reply.
#include <stdio.h>
#if LIBCOM1_USE_DTOSTRE
#include "dtostre_shim.hpp"
#endif

static void emit(const char* line) { puts(line); }

#include "script.hpp"

int main()
{
  script::run();
  return 0;
}
