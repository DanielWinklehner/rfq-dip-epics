/* Portions of this file orignate from Arduino Core, licensed under LGPL 2.1 or a later version
 * https://github.com/arduino/ArduinoCore-avr/blob/master/variants/mega/pins_arduino.h
 *
 * Original Copyright Header:

  pins_arduino.h - Pin definition functions for Arduino
  Part of Arduino - http://www.arduino.cc/

  Copyright (c) 2007 David A. Mellis

  This library is free software; you can redistribute it and/or
  modify it under the terms of the GNU Lesser General Public
  License as published by the Free Software Foundation; either
  version 2.1 of the License, or (at your option) any later version.

  This library is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  Lesser General Public License for more details.

  You should have received a copy of the GNU Lesser General
  Public License along with this library; if not, write to the
  Free Software Foundation, Inc., 59 Temple Place, Suite 330,
  Boston, MA  02111-1307  USA
*/

#ifndef ATMEGA2560_PORT_DEF_H
#define ATMEGA2560_PORT_DEF_H

#include <stdio.h>
#include "staticio/pins.hpp"

namespace IO {
namespace Pin {

static const Pin_t pA00{ GpioPinAnalog(F, 0, 0) }; // PF0, ADC0
static const Pin_t pA01{ GpioPinAnalog(F, 1, 1) }; // PF1, ADC1
static const Pin_t pA02{ GpioPinAnalog(F, 2, 2) }; // PF2, ADC2
static const Pin_t pA03{ GpioPinAnalog(F, 3, 3) }; // PF3, ADC3
static const Pin_t pA04{ GpioPinAnalog(F, 4, 4) }; // PF4, ADC4, TCK
static const Pin_t pA05{ GpioPinAnalog(F, 5, 5) }; // PF5, ADC5, TMS
static const Pin_t pA06{ GpioPinAnalog(F, 6, 6) }; // PF5, ADC6, TDO
static const Pin_t pA07{ GpioPinAnalog(F, 7, 7) }; // PF5, ADC7, TDI

static const Pin_t pA08{ GpioPinAnalog(K, 0, 8) };  // PF0, ADC8, PCINT16
static const Pin_t pA09{ GpioPinAnalog(K, 1, 9) };  // PF1, ADC9, PCINT17
static const Pin_t pA10{ GpioPinAnalog(K, 2, 10) }; // PF2, ADC10, PCINT18
static const Pin_t pA11{ GpioPinAnalog(K, 3, 11) }; // PF3, ADC11, PCINT19
static const Pin_t pA12{ GpioPinAnalog(K, 4, 12) }; // PF4, ADC12, PCINT20
static const Pin_t pA13{ GpioPinAnalog(K, 5, 13) }; // PF5, ADC13, PCINT21
static const Pin_t pA14{ GpioPinAnalog(K, 6, 14) }; // PF5, ADC14, PCINT22
static const Pin_t pA15{ GpioPinAnalog(K, 7, 15) }; // PF5, ADC15, PCINT23

static const Pin_t p00{ GpioPin(E, 0) };          // PE0, RXD0, PCINT8
static const Pin_t p01{ GpioPin(E, 1) };          // PE1, TXD0, PCINT3
static const Pin_t p02{ GpioPinPwm(E, 4, 3, B) }; // PE4, INT4, OC3B
static const Pin_t p03{ GpioPinPwm(E, 5, 3, C) }; // PE5, INT5, OC3C
static const Pin_t p04{ GpioPinPwm(G, 5, 0, B) }; // PG5, OC0B
static const Pin_t p05{ GpioPinPwm(E, 3, 3, A) }; // PE3, AIN1, OC3A

static const Pin_t p06{ GpioPinPwm(H, 3, 4, A) }; // PH3, OC4A, PCINT8
static const Pin_t p07{ GpioPinPwm(H, 4, 4, B) }; // PH4, OC4B
static const Pin_t p08{ GpioPinPwm(H, 5, 4, C) }; // PH5, OC4C
static const Pin_t p09{ GpioPinPwm(H, 6, 2, B) }; // PH6, OC2B
static const Pin_t p10{ GpioPinPwm(B, 4, 2, A) }; // PB4, OC2A, PCINT4

static const Pin_t p11{ GpioPinPwm(B, 5, 1, A) }; // PB5, OC1A, PCINT5
static const Pin_t p12{ GpioPinPwm(B, 6, 1, B) }; // PB6, OC1B, PCINT6
static const Pin_t p13{ GpioPinPwm(B, 7, 0, A) }; // PB7, OC0A, PCINT7
static const Pin_t p14{ GpioPin(J, 1) };          // PJ1, TXD3, PCINT10
static const Pin_t p15{ GpioPin(J, 0) };          // PJ0, RXD3, PCINT9

static const Pin_t p16{ GpioPin(H, 1) }; // PH1, TXD2
static const Pin_t p17{ GpioPin(H, 0) }; // PH0, RXD2
static const Pin_t p18{ GpioPin(D, 3) }; // PD3, INT3, TXD1
static const Pin_t p19{ GpioPin(D, 2) }; // PD2, INT2, RXD1
static const Pin_t p20{ GpioPin(D, 1) }; // PD1, INT1, SDA

static const Pin_t p21{ GpioPin(D, 0) }; // PD0, INT0, SCL
static const Pin_t p22{ GpioPin(A, 0) }; // PA0, AD0
static const Pin_t p23{ GpioPin(A, 1) }; // PA1, AD1
static const Pin_t p24{ GpioPin(A, 2) }; // PA2, AD2
static const Pin_t p25{ GpioPin(A, 3) }; // PA3, AD3

static const Pin_t p26{ GpioPin(A, 4) }; // PA4, AD4
static const Pin_t p27{ GpioPin(A, 5) }; // PA5, AD5
static const Pin_t p28{ GpioPin(A, 6) }; // PA6, AD6
static const Pin_t p29{ GpioPin(A, 7) }; // PA7, AD7
static const Pin_t p30{ GpioPin(C, 7) }; // PC7, A15

static const Pin_t p31{ GpioPin(C, 6) }; // PC6, A14
static const Pin_t p32{ GpioPin(C, 5) }; // PC5, A13
static const Pin_t p33{ GpioPin(C, 4) }; // PC4, A12
static const Pin_t p34{ GpioPin(C, 3) }; // PC3, A11
static const Pin_t p35{ GpioPin(C, 2) }; // PC2, A10

static const Pin_t p36{ GpioPin(C, 1) }; // PC1, A9
static const Pin_t p37{ GpioPin(C, 0) }; // PC0, A8
static const Pin_t p38{ GpioPin(D, 7) }; // PD7, T0
static const Pin_t p39{ GpioPin(G, 2) }; // PG2, ALE
static const Pin_t p40{ GpioPin(G, 1) }; // PG1, RD

static const Pin_t p41{ GpioPin(G, 0) };          // PG0, WR
static const Pin_t p42{ GpioPin(L, 7) };          // PL7
static const Pin_t p43{ GpioPin(L, 6) };          // PL6
static const Pin_t p44{ GpioPinPwm(L, 5, 5, C) }; // PL5, OC5C
static const Pin_t p45{ GpioPinPwm(L, 4, 5, B) }; // PL4, OC5B

static const Pin_t p46{ GpioPinPwm(L, 3, 5, A) }; // PL3, OC5A
static const Pin_t p47{ GpioPin(L, 2) };          // PL2, T5
static const Pin_t p48{ GpioPin(L, 1) };          // PL1, ICP5
static const Pin_t p49{ GpioPin(L, 0) };          // PL0, ICP4
static const Pin_t p50{ GpioPin(B, 3) };          // PB3, MISO, PCINT3

static const Pin_t p51{ GpioPin(B, 2) }; // PB2, MOSI, PCINT2
static const Pin_t p52{ GpioPin(B, 1) }; // PB1, SCK, PCINT1
static const Pin_t p53{ GpioPin(B, 0) }; // PB0, SS, PCINT0

#define pSDA pPin20 // I2C SDA
#define pSCL pPin21 // I2C SCL

#define pSS pPin53   // SPI SS
#define pMOSI pPin51 // SPI MOSI
#define pMISO pPin50 // SPI MISO
#define pSCK pPin52  // SPI SCK

} // namespace detail
} // namespace IO

#endif // ATMEGA2560_PORT_DEF_H
