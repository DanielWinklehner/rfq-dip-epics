#include <avr/interrupt.h>
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
#include "digital_io.hpp"

// Suggestion: Watchdog Timer
// Enable wdt in main, use it as a reset point, if the AVR ever malfunctions.
// Likely to set as Interrupt and System Reset Mode. Interrupt trigger would
// save current pin out states to EEPROM. On reset, it would read EEPROM for
// the last used values, and set accordingly. Not sure if EEPROM values should
// be reset after reading.

static FILE mystdout;

// RY - Don't make these mistakes. Debug hard.
/*
 * ---------- IMPORTANT ----------
 * IMPORTANT: ALWAYS MAKE SURE 'num_cmds' IS CORRECT.
 * POSSIBLE FAILURE:
 * - Reading memory beyond intended
 * - Not checking enough commands
 *
 * IMPORTANT: ALWAYS MAKE SURE THERE ARE ENOUGH VARIABLES IN 'eval::eval' TO
 * SATISFY THE SSCANF.
 * POSSIBLE FAILURES:
 * - Undefined behavior (b/c sscanf is prone to it)
 * ----------*---------*----------
 */

#pragma message "Ensure num_cmds is set correctly in " __FILE__
const uint8_t num_cmds = 2;
const Eval::CMDEntry eval_cmds[num_cmds] = {
  { 1,
    "GD?%hhu",
    [](const char* src) {
      // get_digital_pin
      uint8_t pin;
      sscanf(src, "GD?%hhu", &pin);

      DEBUG_PRINT("Query: Get pin: %d\n", pin);

      // Response
      printf("GD:%d:%hhu\n", pin, IO::get_digital(pin));
    } },

  { 2,
    "SD!%hhu:%hhu",
    [](const char* src) {
      // set_digital_pin
      uint8_t pin, value;
      sscanf(src, "SD!%hhu:%hhu", &pin, &value);

      IO::set_digital(pin, (bool)value);

      DEBUG_PRINT("Query: Set pin: %d, Value: %d\n", pin, value);
    } },
};

int
main(void)
{
  USART::init();

  // Pin setup
  IO::ddr_digital(5, IO::DDR::OUTPUT);
  IO::ddr_digital(10, IO::DDR::INPUT);

  // Enable fprint to USART
  fdev_setup_stream(&mystdout, USART::put_char, NULL, _FDEV_SETUP_WRITE);
  stdout = &mystdout;

  // Enable global interrupts
  sei();

  for (;;) {
    if (USART::rx_done_flag == 1) {
      USART::get_string();

      // TODO: if status is fail, and there have been multiple failed attempts,
      // Pause the code, and let the watchdog reset the AVR.
      uint8_t status = Eval::eval(USART::eval_str, eval_cmds, num_cmds);
    }
  }

  return 0;
}
