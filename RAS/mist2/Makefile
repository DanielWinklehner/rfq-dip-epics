# MIST-2 RAS development stack (React Automation Studio V8.1.0).
#   make dev-up     build if needed, check ports, start; then open
#                   http://localhost:3000/ (RAS_HTTP_PORT in .env)
#   make dev-down   stop and remove the containers (images are kept)
#   make dev-logs   follow the logs of all services
#   make build      build the images (dev-up does this too, cached)
# All settings are in .env, created from env.template on first use.

# The profile "build" is on in every call: pvserver and frontend name the base images of that
# profile in additional_contexts, and Compose 2.40.3 (Ubuntu 26.04's package) refuses the project
# file without it, also for up, down and logs: 'service "pvserver" declares unknown service
# "epicsbase" as additional contexts' (seen on the lab computer, 2026-11-25; Compose v5 on the
# development PC accepts both forms). The services to run are named, so the two base images
# are still built and never started.
COMPOSE := docker compose -f compose.dev.yaml --profile build
RUN := pvserver frontend nginx
SHELL := /bin/bash

.PHONY: build dev-up dev-down dev-logs check-ports

.env:
	cp env.template .env
	@echo "created .env from env.template"

# The base images (epicsbase, node_cache) are in the "build" profile: they are
# built but never started. The first build takes 20 to 30 minutes.
build: .env
	$(COMPOSE) build

check-ports: .env
	tools/check-ports.sh

dev-up: build check-ports
	$(COMPOSE) up -d --no-build $(RUN)
	tools/wait-for-gui.sh

dev-down: .env
	$(COMPOSE) down --remove-orphans

dev-logs: .env
	$(COMPOSE) logs -f $(RUN)
