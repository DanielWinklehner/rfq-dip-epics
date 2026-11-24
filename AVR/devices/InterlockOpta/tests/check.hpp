#ifndef interlock_opta_tests_check_hpp
#define interlock_opta_tests_check_hpp

// A minimal check macro for the PC tests: prints the failed condition with its line and counts it.

#include <stdio.h>

static int g_failures = 0;
static int g_checks = 0;

#define CHECK(cond)                                                                       \
  do {                                                                                    \
    ++g_checks;                                                                           \
    if (!(cond)) {                                                                        \
      ++g_failures;                                                                       \
      printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);                              \
    }                                                                                     \
  } while (0)

#define CHECK_MSG(cond, ...)                                                              \
  do {                                                                                    \
    ++g_checks;                                                                           \
    if (!(cond)) {                                                                        \
      ++g_failures;                                                                       \
      printf("FAIL %s:%d: %s: ", __FILE__, __LINE__, #cond);                              \
      printf(__VA_ARGS__);                                                                \
      printf("\n");                                                                       \
    }                                                                                     \
  } while (0)

static int finish(const char* name)
{
  if (g_failures != 0) {
    printf("%s: %d of %d checks FAILED\n", name, g_failures, g_checks);
    return 1;
  }
  printf("%s: all %d checks passed\n", name, g_checks);
  return 0;
}

#endif
