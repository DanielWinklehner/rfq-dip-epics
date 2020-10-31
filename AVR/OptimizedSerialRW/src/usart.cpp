#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "usart.hpp"

namespace USART {

volatile char rx_buffer[USART_RX_BUFFER_SIZE]{ 0 };
volatile uint8_t rx_buffer_p{ 0 };
volatile uint8_t rx_done_flag{ 0 };

char eval_str[USART_RX_BUFFER_SIZE]{ 0 };
char trash{ 0 };

void
init()
{
  // Enable asyncromous USART mode
  UCSR0C &= ~((1 << UMSEL01) | (1 << UMSEL00));

  // Enable Double Speed, requires Async mode
  UCSR0A |= (1 << U2X0);

  // Set Buad rate
  // F_CPU and BAUD defined in CMake file
  // 2* bc of U2X enabled
  constexpr uint16_t baud_setting =
    (2 * ((((F_CPU / 16) + (BAUD / 2)) / (BAUD)) - 1));
  UBRR0H = baud_setting >> 8;
  UBRR0L = baud_setting;

  // USART Frame Format:
  // Async, Even Parity, 1 Stop bit, 8-bit data, Polarity set to 0 in async mode
  UCSR0C = 0b00100110;
  UCSR0B &= ~(1 << UCSZ02); // 8 Bit Char Size

  // Enable RX interrupts
  UCSR0B |= (1 << RXCIE0);

  // Enable RX and TX on USART0
  UCSR0B |= (1 << RXEN0) | (1 << TXEN0);
}

void
send(unsigned char data)
{
  // Do nothing until UDR is ready for more data to be written to it
  while (!(UCSR0A & (1 << UDRE0))) {
    asm volatile("nop");
  }
  UDR0 = data;
}

void
send(char* data, size_t size)
{
  for (uint8_t i = 0; i < size; ++i) {
    send(data[i]);
  }
}

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"
int
put_char(char data, FILE* stream)
{
  send(data);
  return 0;
}
#pragma GCC diagnostic pop

void
get_string()
{
  cli();

  // Clear the current string.
  memset(eval_str, 0, USART_RX_BUFFER_SIZE);

  // Copy contents to retval, clear the buffer, and accept new chars.
  for (int i = 0; i < USART_RX_BUFFER_SIZE; ++i) {
    eval_str[i] = rx_buffer[i];
    rx_buffer[i] = 0;
  }

  rx_buffer_p = 0;
  rx_done_flag = 0;
  sei();
}

// Interupt for receiving data
ISR(USART0_RX_vect, ISR_BLOCK)
{
  // Note: This function is blocking if the current string has not been
  // fully processed yet.
  if (rx_done_flag == 0) {
    rx_buffer[rx_buffer_p] = UDR0;

    if (rx_buffer[rx_buffer_p] == '\n') {
      rx_done_flag = 1;
    }

    ++rx_buffer_p;

    // Void input if more than BufferSize chars.
    if (rx_buffer_p == USART_RX_BUFFER_SIZE) {
      rx_buffer_p = 0;
      rx_done_flag = 0;

      // Memset to 0
      for (int i = 0; i < USART_RX_BUFFER_SIZE; ++i) {
        rx_buffer[i] = 0;
      }
    }
  } else {
    // UDR0 must be read in order to reset interrupt vector.
    trash = UDR0;
  }
}

} // namespace USART
