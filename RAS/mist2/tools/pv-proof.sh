#!/usr/bin/env bash
# Proves that the running pvServer of the MIST-2 RAS stack delivers PVs from
# the two IOCs on a Docker bridge network:
#   <prefix>.11  IOC-RACK:heartbeat  IOC-RACK:mode
#   <prefix>.12  IOC-HV:heartbeat    IOC-HV:mode
# The values are read through pvServer's own client interface: a Socket.IO
# client in a container connects to nginx exactly as the browser does.
#
# usage: tools/pv-proof.sh [PREFIX] [--with-standin-iocs]
#   PREFIX               first three octets of the IOC subnet, default 172.30.0
#                        (the real emulation in emulation/)
#   --with-standin-iocs  start two stand-in soft IOCs on a bridge network
#                        PREFIX.0/24 first and remove them afterwards.
#                        Not allowed for 172.30.0, which belongs to emulation/.
# If pvServer is configured for another subnet than PREFIX, it is restarted
# with EPICS_CA_ADDR_LIST=PREFIX.255 for the test and restored from .env after.
# Prints PASS or FAIL per PV, exit code 1 on any FAIL.
set -uo pipefail
cd "$(dirname "$0")/.."

prefix=172.30.0
standin=0
timeout_s=30
for arg in "$@"; do
    case "$arg" in
        --with-standin-iocs) standin=1 ;;
        -h|--help) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) prefix="$arg" ;;
    esac
done
if ! [[ "$prefix" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
    echo "pv-proof: PREFIX must be three octets, e.g. 172.31.0 (got '$prefix')" >&2
    exit 2
fi
if [ "$standin" = 1 ] && [ "$prefix" = 172.30.0 ]; then
    echo "pv-proof: 172.30.0 is the network of emulation/, no stand-in IOCs there" >&2
    exit 2
fi

# --profile build: Compose 2.40.3 refuses the project file without it (see the Makefile)
compose=(docker compose -f compose.dev.yaml --profile build)
standin_compose=(docker compose -f tools/standin/compose.yaml)
set -a; . ./.env; set +a
want="$prefix.255"
restored=1

cleanup() {
    if [ "$restored" = 0 ]; then
        echo "pv-proof: restoring pvServer to the .env setting EPICS_CA_ADDR_LIST=$EPICS_CA_ADDR_LIST"
        "${compose[@]}" up -d --no-build pvserver >/dev/null 2>&1
    fi
    if [ "$standin" = 1 ]; then
        echo "pv-proof: removing the stand-in IOCs and their network"
        STANDIN_PREFIX="$prefix" "${standin_compose[@]}" down --remove-orphans >/dev/null 2>&1
    fi
}
trap cleanup EXIT

pvserver_id=$("${compose[@]}" ps -q pvserver 2>/dev/null)
if [ -z "$pvserver_id" ]; then
    echo "pv-proof: pvServer is not running, start the stack with 'make -C RAS/mist2 dev-up'" >&2
    standin=0
    exit 1
fi

if [ "$standin" = 1 ]; then
    echo "pv-proof: starting stand-in IOCs on $prefix.0/24 (.11 rack, .12 platform)"
    if ! STANDIN_PREFIX="$prefix" "${standin_compose[@]}" up -d; then
        echo "pv-proof: could not start the stand-in IOCs" >&2
        exit 1
    fi
fi

current=$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$pvserver_id" \
          | sed -n 's/^EPICS_CA_ADDR_LIST=//p')
if [ "$current" != "$want" ]; then
    echo "pv-proof: pvServer uses EPICS_CA_ADDR_LIST=$current, restarting it with $want for this test"
    restored=0
    EPICS_CA_ADDR_LIST="$want" "${compose[@]}" up -d --no-build pvserver || exit 1
fi
echo "pv-proof: pvServer Channel Access: EPICS_CA_AUTO_ADDR_LIST=$EPICS_CA_AUTO_ADDR_LIST EPICS_CA_ADDR_LIST=$want"

echo "pv-proof: reading through http://127.0.0.1:$RAS_HTTP_PORT/pvServer (Socket.IO, as the browser), up to ${timeout_s} s"
docker run --rm --name mist2ras-pv-proof --network host \
    -e NODE_PATH=/ReactApp/node_modules \
    -v "$PWD/tools/pv-proof-client.cjs:/proof/pv-proof-client.cjs:ro" \
    mist2ras-node-cache \
    node /proof/pv-proof-client.cjs "http://127.0.0.1:$RAS_HTTP_PORT" "$timeout_s" \
        IOC-RACK:heartbeat IOC-HV:heartbeat -- IOC-RACK:mode IOC-HV:mode
rc=$?
if [ $rc -eq 0 ]; then echo "pv-proof: PASS"; else echo "pv-proof: FAIL"; fi
exit $rc
