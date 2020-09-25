#ifndef EVAL_HPP
#define EVAL_HPP

#include <stdio.h>

namespace Eval {

typedef void (*eval_func)(const char*);
struct CMDEntry
{
  const int8_t matches;
  const char* match_str;
  const eval_func func;
};

uint8_t
eval(const char* src, const CMDEntry* cmds, const uint8_t num_cmds);

} // namespace Eval

#endif // EVAL_HPP
