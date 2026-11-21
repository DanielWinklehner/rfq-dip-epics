# MIST-2 emulation. Call from the repository root as `make -C emulation <target>`.
# See README.md.

HERE := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
REPO := $(abspath $(HERE)/..)

# Files the tools container writes into the repository belong to the calling user.
export MIST2_UID := $(shell id -u)
export MIST2_GID := $(shell id -g)

COMPOSE := docker compose -f $(HERE)/compose.yaml
TOOLS   := $(COMPOSE) --profile tools run --rm -T tools

.PHONY: build up down restart ps logs ca-proof devtest plan plan-check registry test

build:
	docker build -f $(HERE)/docker/ioc.Dockerfile -t mist2-ioc:dev $(REPO)
	docker build -f $(HERE)/docker/tools.Dockerfile -t mist2-tools:dev $(HERE)/docker

up:
	$(COMPOSE) up -d --wait

down:
	$(COMPOSE) --profile tools --profile plant down --remove-orphans

restart:
	$(COMPOSE) restart
	$(COMPOSE) up -d --wait

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs --no-color

# --- Plant model (sim/README.md, "Plant model") ------------------------------------------------
# `up` starts the emulation without the plant, as before. up-plant starts it with the plant.
# plant-stop stops only the plant: every device goes back to its own behaviour.
.PHONY: up-plant plant-stop plant-logs down-plant

up-plant:
	$(COMPOSE) --profile plant up -d --wait

plant-stop:
	$(COMPOSE) --profile plant stop plant
	$(COMPOSE) --profile plant rm -f plant

plant-logs:
	$(COMPOSE) --profile plant logs --no-color plant

down-plant:
	$(COMPOSE) --profile tools --profile plant down --remove-orphans

ca-proof:
	$(HERE)/tools/ca-proof.sh

devtest:
	@test -n "$(CASE)" || { echo "usage: make -C emulation devtest CASE=<case directory>"; exit 2; }
	$(HERE)/devtest/run.sh $(abspath $(if $(filter /%,$(CASE)),$(CASE),$(REPO)/$(CASE)))

plan:
	$(TOOLS) python plan/build.py

# Runs the parser tests (plan/test_build.py), then builds into a temporary directory in the
# container: plan/out stays untouched.
plan-check:
	@out=$$($(TOOLS) sh -c 'python -m unittest -q plan/test_build.py && python plan/build.py --out "$$(mktemp -d)"' 2>&1); status=$$?; \
	echo "$$out"; \
	if [ $$status -ne 0 ]; then echo "plan-check: FAIL (build.py exit $$status)"; exit 1; fi; \
	if echo "$$out" | grep -q WARNING; then echo "plan-check: FAIL (warnings)"; exit 1; fi; \
	echo "plan-check: OK"

# The device registry of the GUI and the tests, generated from plan/controls.yaml, EPICS/Db and the
# st.cmd files. Fails (and writes nothing) when they disagree.
registry:
	$(TOOLS) python plan/registry.py

test:
	@if [ -d $(REPO)/emulation/tests ]; then \
		$(TOOLS) python -m pytest -p no:cacheprovider emulation/tests; \
	else \
		echo "emulation/tests does not exist yet: the system tests are not there yet"; \
	fi
