#!/bin/bash
# run_sim.sh - the simulator side of the dipolescan case, three processes in one container:
#   the DAQ service with its sim backend   through the dipole case's run_service.sh (the test
#                                          stops and starts it with build/daq-run), port 5000,
#                                          status port 6000
#   the picoammeter simulator              mist2sim with sim.yaml, port 5001, control port 6001
#   the coupling                           coupling.py with coupling.yaml
# When one of them ends by itself, the others are stopped and the container ends with its exit
# code, so that a crash is not hidden.
cd /case || exit 99
pids=()
stop_all() { for p in "${pids[@]}"; do kill -TERM "$p" 2>/dev/null; done; wait; }
trap 'stop_all; exit 0' TERM INT

sh /repo/emulation/devtest/dipole/run_service.sh &
pids+=($!)
python -m mist2sim --config /case/sim.yaml &
pids+=($!)
python /case/coupling.py /case/coupling.yaml &
pids+=($!)

wait -n
status=$?
echo "run_sim: a process ended by itself, exit code $status; stopping the others"
stop_all
exit "$status"
