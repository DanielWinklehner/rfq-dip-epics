// Runs tests/script.hpp on an ATmega2560 (in simavr) with the real avr-libc dtostre() and strtod(),
// i.e. the code path an Arduino Mega uses. Replies go out on USART0, which simavr prints.
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/sleep.h>
#include <stdlib.h>

static void uart_put(char c)
{
  while (!(UCSR0A & (1 << UDRE0))) { }
  UDR0 = c;
}

static void emit(const char* line)
{
  for (; *line != '\0'; ++line)
  { uart_put(*line); }
  uart_put('\n');
}

#include "../script.hpp"

int main()
{
  UCSR0A = (1 << U2X0);
  UBRR0 = 16;                       // 115200 baud at 16 MHz
  UCSR0B = (1 << TXEN0);
  UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);

  script::run();

  // Let the last byte leave, then stop the simulator: sleeping with interrupts off ends simavr.
  while (!(UCSR0A & (1 << UDRE0))) { }
  cli();
  sleep_enable();
  sleep_cpu();
  for (;;) { }
}
