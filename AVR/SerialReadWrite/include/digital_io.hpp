#pragma once

#ifndef PORT_DEF_HPP
#define PORT_DEF_HPP

#include <stdlib.h>
#include <stdio.h>

#if defined(__AVR_ATmega2560__)
#include "port_def_atmega2560.hpp"
#endif

namespace IO {

using namespace IO::detail;

enum DDR
{
  OUTPUT,
  INPUT,
  INPUT_PULLUP,
};

uint8_t
digital_pin_to_bitmask(uint8_t pin);

uint8_t
digital_pin_to_reg_num(uint8_t pin);

volatile uint8_t*
port_input_register(uint8_t reg_num);

volatile uint8_t*
port_output_register(uint8_t reg_num);

volatile uint8_t*
port_ddr_register(uint8_t reg_num);

void
ddr_digital(uint8_t pin, DDR type);

void
set_digital(uint8_t pin, uint8_t boolean);

uint8_t
get_digital(uint8_t pin);

} //namespace IO

#endif // PORT_DEF_HPP
