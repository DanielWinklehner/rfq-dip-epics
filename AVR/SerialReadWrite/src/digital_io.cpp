#include <digital_io.hpp>
#include <avr/pgmspace.h>

uint8_t
IO::digital_pin_to_bitmask(uint8_t pin)
{
  return pgm_read_byte(digital_pin_to_bit_mask_PGM + pin);
}

uint8_t
IO::digital_pin_to_reg_num(uint8_t pin)
{
  return pgm_read_byte(digital_pin_to_port_PGM + pin);
}

volatile uint8_t*
IO::port_input_register(uint8_t reg_num)
{
  return (volatile uint8_t*)(pgm_read_word(port_to_input_PGM + reg_num));
}

volatile uint8_t*
IO::port_output_register(uint8_t reg_num)
{
  return (volatile uint8_t*)(pgm_read_word(port_to_output_PGM + reg_num));
}

volatile uint8_t*
IO::port_ddr_register(uint8_t reg_num)
{
  return (volatile uint8_t*)(pgm_read_word(port_to_ddr_PGM + reg_num));
}

void
IO::ddr_digital(uint8_t pin, DDR type)
{
  uint8_t bit = digital_pin_to_bitmask(pin);
  uint8_t port = digital_pin_to_reg_num(pin);

  volatile uint8_t* ddrxn = port_ddr_register(port);
  volatile uint8_t* portxn = port_output_register(port);

  switch (type) {
    case OUTPUT:
      *ddrxn |= bit;
      break;
    case INPUT:
      *ddrxn &= ~bit;
      *portxn &= ~bit;
      break;
    case INPUT_PULLUP:;
      *ddrxn &= ~bit;
      *portxn |= bit;
      break;
  }
}

void
IO::set_digital(uint8_t pin, uint8_t boolean)
{
  uint8_t bit = digital_pin_to_bitmask(pin);
  uint8_t port = digital_pin_to_reg_num(pin);
  volatile uint8_t* out = port_output_register(port);

  if ((bool)boolean) {
    *out |= bit;
  } else {
    *out &= ~bit;
  }
}

uint8_t
IO::get_digital(uint8_t pin)
{
  uint8_t bit = digital_pin_to_bitmask(pin);
  uint8_t port = digital_pin_to_reg_num(pin);

  return ((*port_input_register(port) & bit) > 0x00);
}
