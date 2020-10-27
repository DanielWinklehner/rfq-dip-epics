#include <avr/pgmspace.h>
#include <stdio.h>

#include "eval.hpp"

uint8_t
Eval::eval(const char* src, const CMDEntry* cmds)
{
  uint8_t retval = 0;

  // Vars = Max number of matches in cmds[]
  int a = 0;
  int b = 0;

  // qCH
  // sCH:1

  // Eval:
  if (sscanf_P(src, PSTR("q%d"), &a) == 1) {
    a = (a - 1) % 3; // For the current setup w/o device name in pv name
    cmds[a].readback();
  } else if (sscanf_P(src, PSTR("s%d:%d"), &a, &b) == 2) {
    a = (a - 1) % 3; // For the current setup w/o device name in pv name
    cmds[a].setpoint(b);
  }

  return retval;
}
