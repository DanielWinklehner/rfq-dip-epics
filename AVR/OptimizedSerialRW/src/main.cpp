#include <avr/interrupt.h>
#include <avr/pgmspace.h>
#include <util/delay.h>
#include <string.h>
#include <stdio.h>

#if defined PRINTF_TRACE && PRINTF_TRACE == 1
#define DEBUG_PRINT(fmt, args...) printf(fmt, ##args)
#else
#define DEBUG_PRINT(fmt, args...)
#endif

#include "usart.hpp"
#include "staticio/io.hpp"
#include "com/com.hpp"
#include "com/eval.hpp"

static FILE mystdout;

float
d1_get()
{
  return IO::Digital::read(IO::Pin::p10);
}

void
d1_set(float setval)
{
  IO::Digital::write(IO::Pin::p05, (int)(setval));
}

float
d2_get()
{
  return IO::Digital::read(IO::Pin::p40);
}

void
d2_set(float setval)
{
  IO::Digital::write(IO::Pin::p30, (int)setval);
}

float
a1_get()
{
  uint16_t val = IO::Analog::read(IO::Pin::pA00);
  return val * (5.0 / 1023.0);
}

void
a1_set(float setval)
{
  IO::Analog::write_pwm(IO::Pin::p09, (uint8_t)setval);
}

static constexpr Comm::ChannelMap<3> lookup{ {
  { 'd', 1, &d1_get, &d1_set },
  { 'd', 2, &d2_get, &d2_set },
  { 'a', 1, &a1_get, &a1_set },
} };

int
main(void)
{
  // Pin setup
  {
    using namespace IO;
    Digital::pin_ddr(Pin::p05, DDR::OUTPUT);
    Digital::pin_ddr(Pin::p10, DDR::INPUT);
    Digital::pin_ddr(Pin::p30, DDR::OUTPUT);
    Digital::pin_ddr(Pin::p40, DDR::INPUT);

    PWM::init_timer(2); // For pin 9
    Digital::pin_ddr(Pin::p09, DDR::OUTPUT);

    Analog::init(); // For A0
  }

  USART::init();

  // Enable printf to USART
  fdev_setup_stream(&mystdout, USART::put_char, NULL, _FDEV_SETUP_WRITE);
  stdout = &mystdout;

  // Enable global interrupts
  sei();

  for (;;) {
    if (USART::rx_done_flag == 1) {
      USART::get_string();

      DEBUG_PRINT("USART Received: %s", USART::eval_str);

      static char write_buf[512]{ 0 };
      uint8_t status = Comm::eval(lookup, USART::eval_str, write_buf);

      DEBUG_PRINT("Eval returned with: %hhu\n", status);

      switch (status) {
        case Comm::PRC_QUERY:
        case Comm::PRC_QALL:
          printf("%s\n", write_buf);
          break;
        case Comm::ERR_PRECISION_TOO_LARGE:
          printf_P(PSTR("ERR2\n"));
          break;
        case Comm::ERR_CHANNEL_LOOKUP:
          printf_P(PSTR("ERR4\n"));
          break;
        case Comm::ERR_UNKNOWN:
          printf_P(PSTR("ERR0\n"));
          break;
        case Comm::PRC_SET:
        default:
          break;
      }
    }
  }

  return 0;
}
