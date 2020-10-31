#include <avr/pgmspace.h>
#include "staticio/gpio.hpp"
#include "staticio/pwm.hpp"
#include "staticio/pins.hpp"

void
IO::Digital::pin_ddr(const Pin::Pin_t& pin, DDR type)
{
  switch (type) {
    case OUTPUT:
      *(pin.ddr) |= (1 << pin.bit);
      break;
    case INPUT:
      *(pin.ddr) &= ~(1 << pin.bit);
      *(pin.port) &= ~(1 << pin.bit);
      break;
    case INPUT_PULLUP:;
      *(pin.ddr) &= ~(1 << pin.bit);
      *(pin.port) |= (1 << pin.bit);
      break;
  }
}

void
IO::Digital::write(const Pin::Pin_t& pin, uint8_t boolean)
{
  if ((bool)boolean) {
    *(pin.port) |= (1 << pin.bit);
  } else {
    *(pin.port) &= ~(1 << pin.bit);
  }
}

uint8_t
IO::Digital::read(const Pin::Pin_t& pin)
{
  return ((*(pin.pin) & (1 << pin.bit)) > 0x00);
}

void
IO::Analog::init()
{
#if defined(__AVR_ATmega2560__)
  // Set ADC Prescaler. On Atmega2560, must be btwn 50kHz and 200kHz.
  // On a 16 Mhz clock, that is a prescalar of 128 to get 125kHz.
  ADCSRA |= (1 << ADPS2) | (1 << ADPS1) | (1 << ADPS0);

  // Set reference voltage to AVCC
  ADMUX |= (1 << REFS0);

  // Free-running mode is not enabled so that the read point can be changed.
  // ADLAR is not set. No left adjustment, get all 10 bits.

  // Enable ADC
  ADCSRA |= (1 << ADEN);
#else
#error "Current selected board does not have IO::Analog::init() defined"
#endif
}

uint16_t
IO::Analog::read(const Pin::Pin_t& pin)
{
#if defined(__AVR_ATmega2560__)
  // Select ADC channel to read from by setting MUX5:0
  //    Set MUX5 if pin >= 8 by first clearing MUX5 and then setting it the 4th
  //    bit from pin
  ADCSRB = (ADCSRB & ~(1 << MUX5)) | (((pin.adc >> 3) & 0x01) << MUX5);

  //    Set MUX4:0 by first clearing MUX bits from ADMUX and then setting bottom
  //    3 bits to correspond with 0-7 and 8-15
  ADMUX = (ADMUX & ~(0x1F)) | (pin.adc & 0x07);

  // Begin ADC conversation
  ADCSRA |= (1 << ADSC);

  // Wait for ADC conversation to finish
  while (bit_is_set(ADCSRA, ADSC))
    asm volatile("nop" ::);

  // ADCL must be read first, which locks the registers, then reading ADCH will
  // unlock the registers.
  uint8_t low = ADCL;
  uint8_t high = ADCH;

  return (high << 8) | low;
#else
#error                                                                         \
  "Current selected board does not have IO::Analog::read(uint8_t pin) defined"
#endif
}

void
IO::Analog::write_pwm(const Pin::Pin_t& pin, uint8_t duty_cycle)
{
  if (pin.com == 0xFF) // NOT A TIMER
    return;

  if (duty_cycle == 0) {
    PWM::disable(pin);
    Digital::write(pin, 0);

  } else if (duty_cycle == 255) {
    PWM::disable(pin);
    Digital::write(pin, 1);

  } else {
    PWM::write(pin, duty_cycle);
  }
}
