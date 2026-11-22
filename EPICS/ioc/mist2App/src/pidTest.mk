# pidTest.mk - builds and runs the test of the PID algorithm alone (pidTest.c), with the host's C
# compiler, without EPICS and without the emulation. From the repository root:
#
#   make -f pidTest.mk -C EPICS/ioc/mist2App/src
#
# The program is written to the temporary directory and deleted after the run.
CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -Werror -O2
PROGRAM := $(or $(TMPDIR),/tmp)/mist2-pidTest-$(shell id -u)

.PHONY: test
test:
	$(CC) $(CFLAGS) -o $(PROGRAM) pidTest.c pid.c -lm
	@status=0; $(PROGRAM) || status=$$?; rm -f $(PROGRAM); exit $$status
