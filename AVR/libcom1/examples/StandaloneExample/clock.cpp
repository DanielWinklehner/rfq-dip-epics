#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/atomic.h>

#include "clock.hpp"

namespace
{
  // The prescaler is set so that timer0 ticks every 64 clock cycles, and the
  // the overflow handler is called every 256 ticks.
  const unsigned long MICROSECONDS_PER_TIMER0_OVERFLOW = ( clockCyclesToMicroseconds( 64 * 256 ) );

  // The whole number of milliseconds per timer0 overflow
  const unsigned long MILLIS_INC = ( MICROSECONDS_PER_TIMER0_OVERFLOW / 1000 );

  // The fractional number of milliseconds per timer0 overflow. Shift right
  // by three to fit these numbers into a byte (for 8 MHz, 12 MHz, and 16 MHz this doesn't lose precision).
  const uint8_t FRACT_INC =  ( ( MICROSECONDS_PER_TIMER0_OVERFLOW % 1000 ) >> 3 );
  const uint8_t FRACT_MAX =  ( 1000 >> 3 );

  // Variables to keep track of time
  volatile unsigned long      timer0_overflow_count;
  volatile unsigned long      timer0_millis;
  uint8_t                     timer0_fract;
}

namespace Clock {
  void init() {
    ATOMIC_BLOCK( ATOMIC_RESTORESTATE )
    {
        // Use Timer0 for the system clock, but configure it so it also supports
        // fast hardware pwm (using phase-correct PWM would mean that Timer0
        // overflowed half as often)

        TCCR0A = 0;     // Clear all settings
        TCCR0B = 0;     // Clear all settings
        TIMSK0 = 0;     // Disable all interrupts
        TCNT0  = 0;     // initialize counter value to 0

        TCCR0A |= (1 << WGM01) | (1 << WGM00);

        // set timer 0 prescale factor to 64
        TCCR0B |= (1 << CS01) | (1 << CS00);

        // enable timer 0 overflow interrupt
        TIMSK0 |= (1 << TOIE0);

        // Reset counters
        timer0_overflow_count = 0;
        timer0_millis = 0;
        timer0_fract = 0;
    }
  }
  
  unsigned long micros() {
    unsigned long m;
    uint8_t t;
    
    ATOMIC_BLOCK( ATOMIC_RESTORESTATE )
    {
        m = timer0_overflow_count;
        t = TCNT0;

        if ( ( TIFR0 & _BV(TOV0) ) && ( t < 255 ) )
        {
            m++;
        }
    }
    
    return ( (m << 8) + t ) * ( 64 / clockCyclesPerMicrosecond() );
  }
}

ISR( TIMER0_OVF_vect )
{
  // Copy these to local variables so they can be stored in registers
  // (volatile variables must be read from memory on every access)
  unsigned long m = timer0_millis;
  uint8_t f = timer0_fract;

  m += MILLIS_INC;
  f += FRACT_INC;
  if ( f >= FRACT_MAX ) {
      f -= FRACT_MAX;
      ++m;
  }

  timer0_fract = f;
  timer0_millis = m;
  timer0_overflow_count++;
}

