#ifndef PWM_HPP
#define PWM_HPP

#include <stdint.h>
#include <util/atomic.h>
#include "staticio/pins.hpp"

#define clear_timer(num)                                                       \
  do {                                                                         \
    TCCR##num##A = 0;                                                          \
    TCCR##num##B = 0;                                                          \
    TIMSK##num = 0;                                                            \
  } while (0);

namespace IO {
namespace PWM {
void
init_timer(uint8_t num);

void
write(const Pin::Pin_t& pin, uint8_t duty_cycle);

void
disable(const Pin::Pin_t& pin);
}
}

#endif // PWM_HPP
