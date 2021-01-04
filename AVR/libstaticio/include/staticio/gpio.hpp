#ifndef GPIO_HPP
#define GPIO_HPP

#include <stdio.h>
#include <avr/io.h>

#include "staticio/pins.hpp"

namespace IO {

enum DDR
{
  OUTPUT,
  INPUT,
  INPUT_PULLUP,
};

class Digital
{
public:
  static void pin_ddr(const Pin::Pin_t& pin, const DDR type);

  static void write(const Pin::Pin_t& pin, uint8_t boolean);

  static uint8_t read(const Pin::Pin_t& pin);
};

class Analog
{
public:
  static void init();

  static uint16_t read(const Pin::Pin_t& pin);

  static void write_pwm(const Pin::Pin_t& pin, uint8_t duly_cycle);

private:
};

} //namespace IO

#endif // GPIO_HPP
