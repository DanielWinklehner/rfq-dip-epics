# Tests of InterlockOpta on a PC (R4 of task T28). No board needed.
#
#   make          a) door logic  b) the device through libcom1  c) the firmware and the
#                 simulator's entry `interlockbox` (emulation/sim/config/rack.yaml) give the
#                 same replies to conversation.txt, line by line
#   make clean
#
# Flags of the library's own tests (AVR/libcom1/tests/Makefile): -Wall -Wextra -Werror, address
# and UB sanitizers, gnu++11 and c++17; plus gnu++14 with -funsigned-char, what the Opta's core
# compiles sketches with (variants/OPTA/cxxflags.txt). LIBCOM1_USE_DTOSTRE is left to the
# library: 0 on a PC as on the Opta (%g).
# c) needs python3 with PyYAML (the simulator's configuration loader).

CXX      ?= g++
PYTHON   ?= python3

ROOT     := ../../../..
LIB      := $(ROOT)/AVR/libcom1
UTIL     := $(ROOT)/AVR/libutil
SIM      := $(ROOT)/emulation/sim

INCLUDES := -I$(LIB) -I$(UTIL)
WARNINGS := -Wall -Wextra -Wno-unused-function -Wno-missing-field-initializers
SANITIZE := -fsanitize=address,undefined -fno-sanitize-recover=all
HEADERS  := ../door_logic.hpp ../interlock_device.hpp box.hpp check.hpp \
            $(wildcard $(LIB)/*.hpp) $(wildcard $(UTIL)/*.hpp)

CONFIGS  := gnu++11 gnu++14u c++17
BUILD    := build

flags_gnu++11  := -std=gnu++11
flags_gnu++14u := -std=gnu++14 -funsigned-char
flags_c++17    := -std=c++17

TESTS := test_door_logic test_device
BINS  := $(foreach c,$(CONFIGS),$(foreach t,$(TESTS),$(BUILD)/$(t)_$(c)))

.PHONY: all test replay clean
all: test replay

test: $(BINS)
	@for t in $(BINS); do echo "== $$t"; ./$$t || exit 1; done
	@echo "a) and b): all configurations passed."

define build_rule
$(BUILD)/$(1)_$(2): $(1).cpp $(HEADERS) | $(BUILD)
	$$(CXX) $$(flags_$(2)) -O1 -g $$(WARNINGS) -Werror $$(SANITIZE) $$(INCLUDES) $$< -o $$@
endef
$(foreach c,$(CONFIGS),$(foreach t,$(TESTS) replay_device,$(eval $(call build_rule,$(t),$(c)))))

replay: $(BUILD)/replay_device_gnu++14u conversation.txt $(SIM)/config/rack.yaml $(SIM)/tools/interlock_replay.py
	./$(BUILD)/replay_device_gnu++14u conversation.txt > $(BUILD)/replay_firmware.txt
	$(PYTHON) $(SIM)/tools/interlock_replay.py --config $(SIM)/config/rack.yaml \
	    --script conversation.txt > $(BUILD)/replay_simulator.txt
	diff $(BUILD)/replay_firmware.txt $(BUILD)/replay_simulator.txt
	@echo "c) firmware and simulator (rack.yaml, interlockbox): $$(wc -l < $(BUILD)/replay_firmware.txt) lines, identical."

$(BUILD):
	mkdir -p $(BUILD)

clean:
	rm -rf $(BUILD)
