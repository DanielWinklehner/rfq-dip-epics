#pragma once

#ifndef CLOCK_HPP
#define CLOCK_HPP

#define clockCyclesPerMicrosecond()         ( F_CPU / 1000000L )
#define clockCyclesToMicroseconds( a )      ( (a) / clockCyclesPerMicrosecond() )
#define microsecondsToClockCycles( a )      ( (a) * clockCyclesPerMicrosecond() )

namespace Clock
{
  void init();
  unsigned long micros();
}

#endif //CLOCK_HPP
