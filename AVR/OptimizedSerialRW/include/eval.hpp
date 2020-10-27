#ifndef EVAL_HPP
#define EVAL_HPP

#include <stdio.h>

namespace Eval {

typedef void (*read_func)();
typedef void (*set_func)(int);
struct CMDEntry
{
  const read_func readback;
  const set_func setpoint;
};

uint8_t
eval(const char* src, const CMDEntry* cmds);

} // namespace Eval

#endif // EVAL_HPP
