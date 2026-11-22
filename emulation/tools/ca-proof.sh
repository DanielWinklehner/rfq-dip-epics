#!/bin/bash
# ca-proof.sh - prove that the three emulated IOCs are reachable by Channel Access
#
# Called by `make -C emulation ca-proof`, with the IOCs up (`make -C emulation up`): rack IOC,
# platform IOC and loop IOC.
# Prints PASS or FAIL per check and exits non-zero on any FAIL.
#
#   a) from a container on mist2ctl, subnet broadcast address, all six PVs, heartbeats count
#   b) unicast to one IOC finds only that IOC's PVs, all addresses find all
#   c) from the host network namespace (as RAS's pvServer), broadcast address, all six PVs
#   d) the IOC logs contain no error line (patterns below)
set -u

SUBNET=${MIST2_SUBNET:-172.30.0}
BCAST=$SUBNET.255
RACK=$SUBNET.11
HV=$SUBNET.12
LOOP=$SUBNET.13
IMAGE=mist2-ioc:dev
NET=mist2ctl
PVS="IOC-RACK:heartbeat IOC-RACK:mode IOC-HV:heartbeat IOC-HV:mode IOC-LOOP:heartbeat IOC-LOOP:mode"

# d) Lines in an IOC log that mean a database, protocol, link or startup error.
# Extended regular expressions, case-insensitive. Colour codes are removed first. Skipped: echoed
# comment lines ("#...") and the echo of the "on error break" command of st.cmd.
ERROR_PATTERNS=(
    'error'                     # iocsh, dbLoadRecords, StreamDevice "... error", asyn errors
    "can't open"                # iocsh: missing startup or port file
    'not found'                 # missing file, record type, device support, driver, link target
    'undefined'                 # macLib: macro ... is undefined
    'no such'                   # missing file or directory
    'illegal'                   # illegal field value
    'invalid'                   # invalid field or link
    'failed'                    # init_record failures, iocInit failure, port configuration
    'unknown'                   # unknown record type, device type or command
    'syntax'                    # database syntax errors
    'command not found'         # iocsh: misspelled command
    'dbLoadRecords: '           # messages from dbLoadRecords itself
    'bad '                      # StreamDevice/asyn "bad ..." messages
)

FAILS=0
pass() { echo "PASS  $*"; }
fail() { echo "FAIL  $*"; FAILS=$((FAILS + 1)); }

# caget with a given address list, from a given network ("mist2ctl" or "host").
ca() {
    local net=$1 addrs=$2; shift 2
    docker run --rm --network "$net" -e EPICS_CA_AUTO_ADDR_LIST=NO -e EPICS_CA_ADDR_LIST="$addrs" \
        --entrypoint caget "$IMAGE" -w 3 "$@" 2>&1
}

# value of one PV in caget output ("NAME VALUE" lines), empty if missing
value() { echo "$2" | awk -v pv="$1" '$1 == pv { print $2 }'; }

# Reads all PVs twice, two seconds apart. Prints PASS/FAIL lines with the given label.
read_all() {
    local label=$1 net=$2 addrs=$3 first second
    first=$(ca "$net" "$addrs" $PVS)
    sleep 2
    second=$(ca "$net" "$addrs" $PVS)
    local pv v1 v2
    for pv in $PVS; do
        v1=$(value "$pv" "$first")
        v2=$(value "$pv" "$second")
        case "$pv" in
            *:heartbeat)
                if [[ "$v1" =~ ^[0-9]+$ && "$v2" =~ ^[0-9]+$ ]] && [ "$v2" -gt "$v1" ]; then
                    pass "$label $pv read, increases ($v1 -> $v2)"
                else
                    fail "$label $pv read and increasing (got '$v1', then '$v2')"
                fi ;;
            *:mode)
                if [ "$v1" = "sim" ]; then pass "$label $pv = '$v1'"
                else fail "$label $pv = 'sim' (got '$v1')"; fi ;;
        esac
    done
}

# found/absent check of one PV through one address list
expect() {
    local label=$1 addrs=$2 pv=$3 want=$4 out
    out=$(ca "$NET" "$addrs" "$pv")
    if [[ "$(value "$pv" "$out")" =~ ^[0-9]+$ ]]; then got=found; else got=absent; fi
    if [ "$got" = "$want" ]; then pass "$label $pv $want"
    else fail "$label $pv expected $want, got $got ($(echo $out))"; fi
}

for c in mist2emu-ioc-rack-1 mist2emu-ioc-hv-1 mist2emu-ioc-loop-1; do
    if [ "$(docker inspect -f '{{.State.Running}}' "$c" 2>/dev/null)" != "true" ]; then
        echo "FAIL  container $c is not running: make -C emulation up"; exit 1
    fi
done

echo "== a) container on $NET, EPICS_CA_ADDR_LIST=$BCAST"
read_all "a)" "$NET" "$BCAST"

echo "== b) unicast"
expect "b) only $RACK:" "$RACK" IOC-RACK:heartbeat found
expect "b) only $RACK:" "$RACK" IOC-HV:heartbeat absent
expect "b) only $HV:" "$HV" IOC-HV:heartbeat found
expect "b) only $HV:" "$HV" IOC-RACK:heartbeat absent
expect "b) $RACK $HV:" "$RACK $HV" IOC-RACK:heartbeat found
expect "b) $RACK $HV:" "$RACK $HV" IOC-HV:heartbeat found
expect "b) only $LOOP:" "$LOOP" IOC-LOOP:heartbeat found
expect "b) only $LOOP:" "$LOOP" IOC-HV:heartbeat absent
expect "b) $RACK $HV $LOOP:" "$RACK $HV $LOOP" IOC-LOOP:heartbeat found

echo "== c) host network namespace, EPICS_CA_ADDR_LIST=$BCAST"
read_all "c)" host "$BCAST"

echo "== d) IOC logs, patterns (case-insensitive):"
printf '      %s\n' "${ERROR_PATTERNS[@]}"
grep_args=()
for p in "${ERROR_PATTERNS[@]}"; do grep_args+=(-e "$p"); done
for c in mist2emu-ioc-rack-1 mist2emu-ioc-hv-1 mist2emu-ioc-loop-1; do
    hits=$(docker logs "$c" 2>&1 | tr -d '\r' | sed 's/\x1b\[[0-9;]*m//g' \
        | grep -v -e '^[[:space:]]*#' -e '^on error ' | grep -E -i "${grep_args[@]}")
    lines=$(docker logs "$c" 2>&1 | wc -l)
    if [ -z "$hits" ]; then pass "d) $c: no error line in $lines log lines"
    else fail "d) $c: error lines:"; echo "$hits" | sed 's/^/        /'; fi
done

echo
if [ $FAILS -eq 0 ]; then echo "ca-proof: all checks PASS"; else echo "ca-proof: $FAILS FAIL"; fi
[ $FAILS -eq 0 ]
