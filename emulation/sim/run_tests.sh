#!/usr/bin/env bash
# Acceptance test of the simulator core and the libcom1 simulator.
#   1. unit tests   2. libcom1 replay against the real library, both number formats
#   3. end-to-end: python -m mist2sim with examples/valvebox.yaml
set -euo pipefail

SIM="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SIM/../.." && pwd)"
LIB="$ROOT/AVR/libcom1"
BUILD="$SIM/build"
PY="${PYTHON:-python3}"
cd "$SIM"
mkdir -p "$BUILD"

echo "== 1. unit tests ($($PY --version))"
$PY -m unittest discover -q -s tests -t tests 2>&1 | tee "$BUILD/unittest.txt" | tail -n 3
UNIT="$(grep -o 'Ran [0-9]* tests' "$BUILD/unittest.txt")"

echo "== 2. libcom1 replay: Python engine against replay_host built from $LIB"
REPLAY=""
for variant in "1 avr" "0 g"; do
  set -- $variant
  bin="$BUILD/replay_host_dtostre$1"
  g++ -std=gnu++11 -O1 -Wall -Wextra -Wno-unused-function -Wno-missing-field-initializers -Werror \
      -DLIBCOM1_USE_DTOSTRE="$1" -I"$LIB" -I"$ROOT/AVR/libutil" "$LIB/tests/replay_host.cpp" -o "$bin"
  "$bin" > "$BUILD/replay_c_$2.txt"
  $PY tools/libcom1_replay.py --format "$2" --script "$LIB/tests/script.hpp" > "$BUILD/replay_py_$2.txt"
  diff "$BUILD/replay_c_$2.txt" "$BUILD/replay_py_$2.txt"
  n="$(wc -l < "$BUILD/replay_c_$2.txt")"
  echo "   LIBCOM1_USE_DTOSTRE=$1 (format $2): $n lines compared, 0 differences"
  REPLAY="$REPLAY $2=$n"
done

echo "== 3. end-to-end"
$PY tools/e2e_valvebox.py

echo
echo "SUMMARY: unit tests OK ($UNIT); replay identical (lines:$REPLAY); end-to-end OK"
