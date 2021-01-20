#include <stdio.h>

#include "clock.hpp"
#include "usart.hpp"
#include "libcom1.hpp"
#include "staticio/io.hpp"

static FILE mystdout;

float
d1_get() { return IO::Digital::read(IO::Pin::p50);}

void
d1_set(float setval) { IO::Digital::write(IO::Pin::p45, (int)(setval));}

float
d2_get() { return IO::Digital::read(IO::Pin::p40); }

void
d2_set(float setval) { IO::Digital::write(IO::Pin::p30, (int)setval); }

using mist1::com1::Channel;
MakeChannelMap(lookup, 2, ({
    Channel{ 'd', 1, &d1_get, &d1_set },
    Channel{ 'd', 2, &d2_get, &d2_set },
  })
);

mist1::com1::IOHandler<128> io_ctx(
  [](){
    while (USART::rx_done_flag != 1)
    { asm volatile("nop"); }
    USART::get_string();
    return USART::eval_str;
  },
  
  [](char* str){ printf("%s\n", str); }
);

mist1::com1::SerialDevice<128,2> device(io_ctx, lookup);

int main() {
  // Pin setup
  {
    using namespace IO;
    Digital::pin_ddr(Pin::p50, DDR::OUTPUT);
    Digital::pin_ddr(Pin::p45, DDR::INPUT);
    Digital::pin_ddr(Pin::p30, DDR::OUTPUT);
    Digital::pin_ddr(Pin::p40, DDR::INPUT);

    //PWM::init_timer(2);
    //Digital::pin_ddr(Pin::p09, DDR::OUTPUT);
    //Analog::init();
  }

  USART::init();
  
  // Enable printf to USART
  fdev_setup_stream(&mystdout, USART::put_char, NULL, _FDEV_SETUP_WRITE);
  stdout = &mystdout;
  
  // Enable global interrupts
  sei();
  
  // Main Loop
  for (;;)
  {
    device.communicate();
  }

  return 0;
}
