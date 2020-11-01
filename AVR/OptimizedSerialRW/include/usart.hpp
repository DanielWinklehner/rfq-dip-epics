#pragma once

#ifndef USART_HPP
#define USART_HPP

#include <stdio.h>

#ifndef USART_RX_BUFFER_SIZE
#define USART_RX_BUFFER_SIZE 16
#endif

namespace USART {

extern volatile char rx_buffer[USART_RX_BUFFER_SIZE];
extern volatile uint8_t rx_buffer_p;
extern volatile uint8_t rx_done_flag;

extern char eval_str[USART_RX_BUFFER_SIZE];
extern char trash;

void
init();

void
send(unsigned char data);

void
send(char* data, size_t size);

void
send(const char* data, size_t size);

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"
// This function is for redirecting stream to UART
int
put_char(char data, FILE* stream);
#pragma GCC diagnostic pop

// Obtain the current string from USART buffer and reset buffer
void
get_string();

} // namespace USART

#endif // USART_HPP
