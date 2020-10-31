#include <avr/interrupt.h>
#include <avr/pgmspace.h>
#include <util/delay.h>
#include <string.h>
#include <stdio.h>

#define PRINTF_TRACE 0

#if PRINTF_TRACE
#define DEBUG_PRINT(fmt, args...) printf(fmt, ##args)
#else
#define DEBUG_PRINT(fmt, args...)
#endif

#include "usart.hpp"
#include "eval.hpp"
#include "staticio/gpio.hpp"
#include "staticio/port_defs.hpp"
#include "staticio/pwm.hpp"

static FILE mystdout;

// qCH
// sCH:1

const Eval::CMDEntry links[] = {
  //readback, setpoint
  { []() {
     // Link1read
     printf("q1:%hhu", IO::Digital::read(IO::Pin::p10));
   },
    [](int setval) {
      // Link1set
      IO::Digital::write(IO::Pin::p05, (bool)setval);
      DEBUG_PRINT("Query: Set Dpin: 5, Value: %d\n", (bool)setval);
    } },

  { []() {
     // Link2read
     printf("q2:%hhu", IO::Digital::read(IO::Pin::p40));
     DEBUG_PRINT("Query: Dpin: 40");
   },
    [](int setval) {
      // Link2set
      IO::Digital::write(IO::Pin::p30, (bool)setval);
      DEBUG_PRINT("Query: Set Dpin: 30, Value: %d\n", (bool)setval);
    } },

  { []() {
     // Link3read
     printf("q3:%u", IO::Analog::read(IO::Pin::pA00));
     DEBUG_PRINT("Query: Apin: A0");
   },
    [](int setval) {
      // Link3set
      IO::Analog::write_pwm(IO::Pin::p09, setval);
      DEBUG_PRINT("Query: Set Apin: 9, Value: %d\n", setval);
    } },
};

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

      // TODO: if status is fail, and there have been multiple failed attempts,
      // Pause the code, and let the watchdog reset the AVR.
      uint8_t status = Eval::eval(USART::eval_str, links);
    }
  }

  return 0;
}
