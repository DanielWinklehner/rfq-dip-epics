#!/bin/sh
# run-ioc.sh - start one MIST-2 IOC
#
#   run-ioc.sh <iocRack|iocHV> <sim|real>
#
# Used by the container entrypoint (emulation/compose.yaml) and on the real Linux computer,
# from the same EPICS top. The top is found from the location of this script, so no generated
# envPaths file is needed (a bind mount of iocBoot would hide it).
set -eu

usage() { echo "usage: $0 <iocRack|iocHV> <sim|real>" >&2; exit 2; }
[ $# -eq 2 ] || usage
IOC=$1
if [ -n "${MIST2_PORTS:-}" ] && [ "$MIST2_PORTS" != "$2" ]; then
    echo "run-ioc.sh: MIST2_PORTS=$MIST2_PORTS in the environment, but '$2' given" >&2; exit 2
fi
MIST2_PORTS=$2

case "$MIST2_PORTS" in
    sim|real) ;;
    *) echo "run-ioc.sh: port mode must be 'sim' or 'real', not '$MIST2_PORTS'" >&2; exit 2 ;;
esac

BOOT=$(cd "$(dirname "$0")" && pwd)
TOP=$(cd "$BOOT/.." && pwd)
# The architecture: EPICS_HOST_ARCH if it is set, else linux-x86_64 if the top is built for it,
# else the one architecture the top is built for (a 32-bit computer: linux-x86).
if [ -z "${EPICS_HOST_ARCH:-}" ]; then
    EPICS_HOST_ARCH=linux-x86_64
    if [ ! -x "$TOP/bin/linux-x86_64/mist2" ]; then
        set -- "$TOP"/bin/*/mist2
        if [ $# -eq 1 ] && [ -x "$1" ]; then EPICS_HOST_ARCH=$(basename "$(dirname "$1")"); fi
    fi
fi
BIN="$TOP/bin/$EPICS_HOST_ARCH/mist2"

[ -f "$BOOT/$IOC/st.cmd" ] || { echo "run-ioc.sh: no IOC '$IOC' ($BOOT/$IOC/st.cmd missing)" >&2; exit 2; }
[ -x "$BIN" ] || { echo "run-ioc.sh: $BIN not found, build the top first (make -C $TOP)" >&2; exit 2; }

# iocsh keeps its command history in the startup directory, which is read-only in the container.
if [ -z "${EPICS_IOCSH_HISTFILE:-}" ] && [ ! -w "$BOOT/$IOC" ]; then
    EPICS_IOCSH_HISTFILE=${TMPDIR:-/tmp}/mist2-$IOC.iocsh_history
    export EPICS_IOCSH_HISTFILE
fi

# Files written at run time (autosave: the limits) go to $MIST2_SAVE/<ioc>, outside the tracked
# sources. Default: $XDG_STATE_HOME/mist2 (~/.local/state/mist2). The emulation sets it to a
# Docker volume (emulation/compose.yaml).
MIST2_SAVE=${MIST2_SAVE:-${XDG_STATE_HOME:-$HOME/.local/state}/mist2}
mkdir -p "$MIST2_SAVE/$IOC" || { echo "run-ioc.sh: cannot create $MIST2_SAVE/$IOC" >&2; exit 2; }

export TOP IOC MIST2_PORTS EPICS_HOST_ARCH MIST2_SAVE
cd "$BOOT/$IOC"
exec "$BIN" st.cmd
