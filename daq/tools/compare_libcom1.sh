#!/usr/bin/env bash
# compare_libcom1.sh - mist2daq's protocol against the REAL libcom1 library, line by line.
#
#   daq/tools/compare_libcom1.sh          (needs g++ and python3; the image mist2-tools:dev has both)
#
# Builds AVR/libcom1/tests/replay_host.cpp with the number format of the Arduino Opta ("%g",
# LIBCOM1_USE_DTOSTRE=0, the format mist2daq uses), runs the fixed conversation of
# AVR/libcom1/tests/script.hpp through it and through tools/libcom1_replay.py, and diffs the two.
# This is what emulation/sim/run_tests.sh does for the simulator.
set -euo pipefail
DAQ="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$DAQ/.." && pwd)"
LIB="$ROOT/AVR/libcom1"
BUILD="$DAQ/build"
mkdir -p "$BUILD"
g++ -std=gnu++11 -O1 -Wall -Wextra -Wno-unused-function -Wno-missing-field-initializers -Werror \
    -DLIBCOM1_USE_DTOSTRE=0 -I"$LIB" -I"$ROOT/AVR/libutil" "$LIB/tests/replay_host.cpp" \
    -o "$BUILD/replay_host_g"
"$BUILD/replay_host_g" > "$BUILD/replay_c_g.txt"
"${PYTHON:-python3}" "$DAQ/tools/libcom1_replay.py" --script "$LIB/tests/script.hpp" > "$BUILD/replay_daq_g.txt"
diff "$BUILD/replay_c_g.txt" "$BUILD/replay_daq_g.txt"
echo "compare_libcom1: $(wc -l < "$BUILD/replay_c_g.txt") lines of the real library (format g), 0 differences"
