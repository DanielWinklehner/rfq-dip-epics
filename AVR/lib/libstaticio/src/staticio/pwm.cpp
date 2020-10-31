#include "staticio/pwm.hpp"

namespace IO {

namespace PWM {

void
init_timer(uint8_t num)
{
  switch (num) {
    case 0:
      clear_timer(0);

      // Prescale Factor: 64, 8-bit Phase Correct PWM Mode
      TCCR0B |= (1 << CS01) | (1 << CS00);
      TCCR0A |= (1 << WGM00);
      break;

    case 1:
      clear_timer(1);

      // Prescale Factor: 64, 8-bit Phase Correct PWM Mode
      TCCR1B |= (1 << CS11) | (1 << CS10);
      TCCR1A |= (1 << WGM10);
      break;

    case 2:
      clear_timer(2);

      // Prescale Factor: 64, 8-bit Phase Correct PWM Mode
      TCCR2B |= (1 << CS22);
      TCCR2A |= (1 << WGM20);
      break;

    case 3:
      clear_timer(3);

      // Prescale Factor: 64, 8-bit Phase Correct PWM Mode
      TCCR3B |= (1 << CS31) | (1 << CS30);
      TCCR3A |= (1 << WGM30);
      break;

    case 4:
      clear_timer(4);

      // Prescale Factor: 64, 8-bit Phase Correct PWM Mode
      TCCR4B |= (1 << CS41) | (1 << CS40);
      TCCR4A |= (1 << WGM40);
      break;

    case 5:
      clear_timer(5);

      // Prescale Factor: 64, 8-bit Phase Correct PWM Mode
      TCCR5B |= (1 << CS51) | (1 << CS50);
      TCCR5A |= (1 << WGM50);
      break;
  }
}

void
write(const Pin::Pin_t& pin, uint8_t duty_cycle)
{
  *(pin.tccr) |= (1 << pin.com);
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { *(pin.ocr) = duty_cycle; }
}

void
disable(const Pin::Pin_t& pin)
{
  *(pin.tccr) &= ~(1 << pin.com);
}

} // namespace detail
} // namespace IO
