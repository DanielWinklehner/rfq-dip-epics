#include <stdio.h>

#include "eval.hpp"

#pragma message "Ensure there are enough vars in " __FILE__                    \
                "::eval() to satisfy sscanf"
uint8_t
Eval::eval(const char* src, const CMDEntry* cmds, const uint8_t num_cmds)
{
  uint8_t retval = 0;

  // Vars = Max number of matches in cmds[]
  int a = 0;
  int b = 0;

  for (uint8_t i = 0; i < num_cmds; ++i) {

    if (sscanf(src, cmds[i].match_str, &a, &b) == cmds[i].matches) {
      cmds[i].func(src);
      break;
    }
  }

  return retval;
}
