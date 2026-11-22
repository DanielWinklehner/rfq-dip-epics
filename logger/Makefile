# MIST-2 data logger. Call from the repository root as `make -C logger <target>`. See README.md.
#   make up       build if needed, write the dashboards, start database, logger and Grafana
#   make down     stop and remove the containers (the data stays in the volumes mist2log-data
#                 and mist2log-grafana)
#   make logs     follow the logs
#   make restart  after `make -C emulation registry`: new PV list and dashboards
#   make test     the logger's tests against the emulation (tests/README.md); starts the emulation
#                 and the logger if they do not run, and stops what it started
#   make read ARGS="TDK:current:read --last 10m"   the reading tool (mist2log/read.py)
# All settings are in .env, created from env.template on first use.

HERE := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
COMPOSE := docker compose -f $(HERE)/compose.yaml --env-file $(HERE)/.env
SHELL := /bin/bash

.PHONY: build up down logs ps dashboards test read restart

$(HERE)/.env:
	cp $(HERE)/env.template $(HERE)/.env
	@echo "created logger/.env from env.template"

build: $(HERE)/.env
	$(COMPOSE) build logger

# The dashboards come from the registry; Grafana rereads them within 30 s.
dashboards: $(HERE)/.env
	@set -a; . $(HERE)/.env; set +a; cd $(HERE) && python3 mist2log/dashboards.py "$${MIST2LOG_REGISTRY_FILE}" build/dashboards

up: build dashboards
	$(COMPOSE) up -d --wait

restart: dashboards
	$(COMPOSE) restart logger

down: $(HERE)/.env
	$(COMPOSE) down --remove-orphans

logs: $(HERE)/.env
	$(COMPOSE) logs -f

ps: $(HERE)/.env
	$(COMPOSE) ps

read: $(HERE)/.env
	@set -a; . $(HERE)/.env; set +a; docker run --rm -i --network host -e MIST2LOG_DB_PORT -e MIST2LOG_READER_PASSWORD \
	    mist2log:1 python -m mist2log.read $(ARGS)

test: $(HERE)/.env
	@$(HERE)/tests/run.sh $(ARGS)
