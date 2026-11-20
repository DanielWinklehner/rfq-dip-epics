# Tests for libcom1.
#
#   make            unit tests on this PC, all four configurations, with sanitizers
#   make avr-sim    run the same conversation on a simulated ATmega2560 (real avr-libc) and on the
#                   PC and compare the replies line by line. Needs avr-g++, avr-libc and simavr
#                   (Debian/Ubuntu: apt install gcc-avr avr-libc simavr).
#   make clean

CXX      ?= g++
AVR_CXX  ?= avr-g++
SIMAVR   ?= simavr

INCLUDES := -I.. -I../../libutil
WARNINGS := -Wall -Wextra -Wno-unused-function -Wno-missing-field-initializers
SANITIZE := -fsanitize=address,undefined -fno-sanitize-recover=all
HEADERS  := $(wildcard ../*.hpp) $(wildcard ../../libutil/*.hpp) dtostre_shim.hpp script.hpp

# gnu++11 is what the Arduino AVR core compiles sketches with.
STDS     := gnu++11 c++17
BUILD    := build

UNIT_BINS := $(foreach s,$(STDS),$(BUILD)/test_$(s)_snprintf $(BUILD)/test_$(s)_dtostre)

.PHONY: all test avr-sim clean
all: test

test: $(UNIT_BINS)
	@for t in $(UNIT_BINS); do echo "== $$t"; ./$$t || exit 1; done
	@echo "All unit test configurations passed."

$(BUILD)/test_%_snprintf: test_libcom1.cpp $(HEADERS) | $(BUILD)
	$(CXX) -std=$* -O1 -g $(WARNINGS) -Werror $(SANITIZE) -DLIBCOM1_USE_DTOSTRE=0 $(INCLUDES) $< -o $@

$(BUILD)/test_%_dtostre: test_libcom1.cpp $(HEADERS) | $(BUILD)
	$(CXX) -std=$* -O1 -g $(WARNINGS) -Werror $(SANITIZE) -DLIBCOM1_USE_DTOSTRE=1 $(INCLUDES) $< -o $@

# --- ATmega2560 in simavr versus the PC -----------------------------------------------------------

AVR_FLAGS := -std=gnu++11 -Os -mmcu=atmega2560 -DF_CPU=16000000UL -DLIBCOM1_USE_DTOSTRE=1 \
             -fno-threadsafe-statics -fno-exceptions -ffunction-sections -fdata-sections \
             -Wl,--gc-sections

$(BUILD)/sim.elf: avr_sim/sim_main.cpp $(HEADERS) | $(BUILD)
	$(AVR_CXX) $(AVR_FLAGS) $(WARNINGS) -Werror $(INCLUDES) $< -o $@ -lm

$(BUILD)/replay_host: replay_host.cpp $(HEADERS) | $(BUILD)
	$(CXX) -std=gnu++11 -O1 -g $(WARNINGS) -Werror $(SANITIZE) -DLIBCOM1_USE_DTOSTRE=1 $(INCLUDES) $< -o $@

avr-sim: $(BUILD)/sim.elf $(BUILD)/replay_host
	./$(BUILD)/replay_host > $(BUILD)/host.txt
	@# simavr colours the UART output and prints a '.' for the line feed: strip both
	timeout 120 $(SIMAVR) -m atmega2560 -f 16000000 $(BUILD)/sim.elf 2>&1 \
	  | sed -e 's/\x1b\[[0-9;]*m//g' -e 's/\.$$//' | grep -v '^$$' | sed '/^DONE$$/q' > $(BUILD)/avr.txt
	@grep -q '^DONE$$' $(BUILD)/avr.txt || { echo "The simulated firmware did not finish"; exit 1; }
	diff $(BUILD)/host.txt $(BUILD)/avr.txt
	@echo "ATmega2560 (simavr) and PC replies are identical: $$(wc -l < $(BUILD)/avr.txt) lines."

$(BUILD):
	mkdir -p $(BUILD)

clean:
	rm -rf $(BUILD)
