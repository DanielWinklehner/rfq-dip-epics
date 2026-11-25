#!/usr/bin/env bash
# Checks that the ports of the MIST-2 RAS stack are free before it starts.
# The stack uses the host network, so a taken port would make a service fail.
# Ports come from .env. Exit code 1 if a port is taken by something else.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

# --profile build: Compose 2.40.3 refuses the project file without it (see the Makefile)
if [ -n "$(docker compose -f compose.dev.yaml --profile build ps -q 2>/dev/null)" ]; then
    echo "check-ports: the mist2ras stack is already running, ports not checked"
    exit 0
fi

taken=0
for entry in "tcp $RAS_HTTP_PORT nginx (browser URL)" \
             "tcp $RAS_VITE_PORT Vite development server" \
             "tcp $pvServerPort pvServer"; do
    read -r proto port what <<<"$entry"
    if ss -Hltn "sport = :$port" | grep -q .; then
        echo "check-ports: port $proto/$port for $what is taken:"
        ss -Hltnp "sport = :$port" | sed 's/^/    /'
        taken=1
    else
        echo "check-ports: $proto/$port free ($what)"
    fi
done
# pvServer's Channel Access client uses ephemeral UDP and TCP ports only.
exit $taken
