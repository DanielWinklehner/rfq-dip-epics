#!/bin/sh
# run_service.sh - mist2daq with the sim backend as the simulator of the dipole case.
#
# The test stops the service by writing "stop" into build/daq-run (SIGTERM, as systemctl stop
# does) and starts it again by writing "run". A service that ends by itself ends the container
# (with its exit code), so a crash is not hidden by a restart.
ctl=/case/build/daq-run
echo run > "$ctl"
cd /repo/daq || exit 99
pid=
trap 'if [ -n "$pid" ]; then kill -TERM "$pid"; wait "$pid"; fi; exit 0' TERM INT
while true; do
    if [ "$(cat "$ctl" 2>/dev/null)" = "stop" ]; then
        sleep 0.1
        continue
    fi
    python -m mist2daq --config /case/daq.yaml &
    pid=$!
    while kill -0 "$pid" 2>/dev/null; do
        sleep 0.1
        if [ "$(cat "$ctl" 2>/dev/null)" = "stop" ]; then
            kill -TERM "$pid"
            wait "$pid"
            echo "devtest: service stopped on request"
            pid=
            continue 2
        fi
    done
    wait "$pid"
    status=$?
    echo "devtest: service ended by itself, exit code $status"
    exit "$status"
done
