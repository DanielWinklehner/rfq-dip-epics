#ifndef PINS_HPP
#define PINS_HPP

#include <avr/io.h>
#include <stdio.h>

#define GpioPin(portLtr, bitNbr)                                               \
  &(DDR##portLtr), &(PORT##portLtr), &(PIN##portLtr), bitNbr, 0xFF, 0, 0, 0xFF

#define GpioPinAnalog(portLtr, bitNbr, adcNbr)                                 \
  &(DDR##portLtr), &(PORT##portLtr), &(PIN##portLtr), bitNbr, adcNbr, 0, 0, 0xFF

#define GpioPinPwm(portLtr, bitNbr, timer, channel)                            \
  &(DDR##portLtr), &(PORT##portLtr), (&PIN##portLtr), bitNbr, 0xFF,            \
    (volatile uint16_t*)&(OCR##timer##channel), &(TCCR##timer##A),             \
    COM##timer##channel##1,

namespace IO {
namespace Pin {

using Reg8p_t = volatile uint8_t*;
using Reg16p_t = volatile uint16_t*;

struct Pin_t
{
  Reg8p_t ddr;  // Data direction register
  Reg8p_t port; // Port data register
  Reg8p_t pin;  // Pin input register
  uint8_t bit;  // Bit within ddr
  uint8_t adc;  // ADC Channel
  Reg16p_t ocr; // Output compare register (Timer)
  Reg8p_t tccr; // Timer control register
  uint8_t com;  // Compare output more (Timer)
};

} // namespace Pin

} // namespace IO

#endif // PINS_HPP
