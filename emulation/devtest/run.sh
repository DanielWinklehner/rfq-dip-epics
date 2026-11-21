#!/bin/bash
# run.sh - test one device database against one device simulator, in isolation
#
#   emulation/devtest/run.sh <case-directory> [pytest arguments]
#
# The case directory holds:
#   sim.yaml   simulator configuration, started as  python -m mist2sim --config /case/sim.yaml
#   sim.cmd    optional, one line: replaces that command
#   ioc.cmd    iocsh lines of this case (asyn ports, dbLoadRecords). Macros: $(SIM_HOST),
#              $(MIST2_DB) (EPICS/Db), $(CASE_DIR) (the case directory in the IOC)
#   test_*.py  pytest files. Environment: SIM_HOST, IOC_HOST, DEVTEST_BUILD (the build/ directory
#              of the case) and Channel Access variables that point at this case's IOC only
#
# Every run is its own Compose project on its own Docker network, so runs in parallel (also from
# different worktrees) do not collide. The IOC and simulator logs are written to
# <case>/build/ioc.log and <case>/build/sim.log while the test runs (colour codes removed).
# Everything is torn down at the end. Exit code: that of pytest, or 99 when the harness itself failed before pytest ran.
set -u

usage() { echo "usage: $0 <case-directory> [pytest arguments]" >&2; exit 99; }
[ $# -ge 1 ] || usage
[ -d "$1" ] || { echo "run.sh: no case directory '$1'" >&2; exit 99; }
CASE=$(cd "$1" && pwd)
shift
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)

[ -f "$CASE/ioc.cmd" ] || { echo "run.sh: $CASE/ioc.cmd missing" >&2; exit 99; }
if [ -f "$CASE/sim.cmd" ]; then
    SIM=$(grep -v '^[[:space:]]*\(#\|$\)' "$CASE/sim.cmd" | head -n 1)
else
    [ -f "$CASE/sim.yaml" ] || { echo "run.sh: neither sim.yaml nor sim.cmd in $CASE" >&2; exit 99; }
    SIM="python -m mist2sim --config /case/sim.yaml"
fi

NAME=$(basename "$CASE" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9\n' '-' | cut -c1-20)
PROJECT="mist2dev-${NAME}-$(od -An -N4 -tx4 /dev/urandom | tr -d ' ')"
export DEVTEST_REPO=$REPO DEVTEST_CASE=$CASE DEVTEST_SIM=$SIM
export MIST2_UID=$(id -u) MIST2_GID=$(id -g)
COMPOSE=(docker compose -p "$PROJECT" -f "$HERE/compose.yaml")

BUILD=$CASE/build
mkdir -p "$BUILD"
{ echo "on error break"; cat "$CASE/ioc.cmd"; } > "$BUILD/ioc.cmd"   # loaded by st.cmd
: > "$BUILD/ioc.log"
: > "$BUILD/sim.log"

FOLLOWERS=()
teardown() {
    "${COMPOSE[@]}" --profile test stop -t 5 >/dev/null 2>&1
    for pid in "${FOLLOWERS[@]}"; do wait "$pid" 2>/dev/null; done
    "${COMPOSE[@]}" --profile test down -v --remove-orphans -t 5 >/dev/null 2>&1
}
trap teardown EXIT
trap 'exit 130' INT TERM

log() { echo "devtest[$PROJECT]: $*"; }
follow() {  # service -> log file, follows until the container stops; iocsh colour codes removed
    "${COMPOSE[@]}" logs -f --no-color --no-log-prefix "$1" 2>&1 | sed -u 's/\x1b\[[0-9;]*[A-Za-z]//g' >> "$2" &
    FOLLOWERS+=($!)
}
running() { [ -n "$("${COMPOSE[@]}" ps -q --status running "$1")" ]; }
fail() {
    log "$*"
    log "last lines of build/sim.log:"; tail -n 15 "$BUILD/sim.log" | sed 's/^/    /'
    log "last lines of build/ioc.log:"; tail -n 15 "$BUILD/ioc.log" | sed 's/^/    /'
    exit 99
}

log "case $CASE"
log "simulator: $SIM"
"${COMPOSE[@]}" up -d sim >/dev/null 2>&1 || fail "simulator container did not start"
follow sim "$BUILD/sim.log"

# The simulator is ready when it listens on a TCP port (so the IOC finds it at its first try).
for i in $(seq 1 60); do
    running sim || fail "simulator exited"
    "${COMPOSE[@]}" exec -T sim sh -c 'cat /proc/net/tcp /proc/net/tcp6 2>/dev/null | awk "\$4 == \"0A\"" | grep -q .' && break
    [ "$i" -eq 60 ] && fail "simulator does not listen on a TCP port after 30 s"
    sleep 0.5
done

"${COMPOSE[@]}" up -d ioc >/dev/null 2>&1 || fail "IOC container did not start"
follow ioc "$BUILD/ioc.log"

for i in $(seq 1 60); do
    running ioc || fail "IOC exited"
    "${COMPOSE[@]}" exec -T -e EPICS_CA_AUTO_ADDR_LIST=NO -e EPICS_CA_ADDR_LIST=127.0.0.1 ioc \
        caget -w 1 DEVTEST:heartbeat >/dev/null 2>&1 && break
    [ "$i" -eq 60 ] && fail "IOC does not answer DEVTEST:heartbeat after 60 s"
done
log "IOC and simulator up, running pytest"

"${COMPOSE[@]}" --profile test run --rm -T test python -m pytest -p no:cacheprovider "$@"
STATUS=$?
log "pytest exit code $STATUS, logs in $BUILD"
exit $STATUS
