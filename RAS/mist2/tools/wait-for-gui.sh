#!/usr/bin/env bash
# Waits until nginx serves the page and Vite serves its JavaScript entry point.
# Exit code 1 if that does not happen within 120 s.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
url="http://localhost:$RAS_HTTP_PORT"
echo "waiting for $url/ ..."
for _ in $(seq 1 120); do
    if curl -sf -o /dev/null "$url/" && curl -sf -o /dev/null "$url/src/main.jsx"; then
        echo "MIST-2 GUI is up: $url/"
        exit 0
    fi
    sleep 1
done
echo "the GUI did not answer within 120 s, see 'make dev-logs'" >&2
exit 1
