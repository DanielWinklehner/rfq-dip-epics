# MIST-2 GUI (React Automation Studio V8.1.0)

Development stack, inside WSL2:

    git submodule update --init RAS/mist2/submodules/React-Automation-Studio
    make -C RAS/mist2 dev-up      # first build 20 to 30 minutes
    # open http://localhost:3000/ in the Windows browser
    make -C RAS/mist2 dev-logs
    make -C RAS/mist2 dev-down

Settings, including all Channel Access settings, are in `RAS/mist2/.env`
(created from `env.template`). Services, all on the host network:

| Service | Port | Purpose |
|---|---|---|
| `nginx` | tcp 3000 (all interfaces) | the URL the browser opens; routes `/socket.io` and `/api` to pvServer, everything else to Vite |
| `frontend` | tcp 3001 (127.0.0.1 only) | Vite development server, serves `ReactApp/src` and the RAS sources with hot reload |
| `pvserver` | tcp 9001 (all interfaces), udp 5065 (CA repeater) | Channel Access client, Socket.IO server for the browser |

`tools/pv-proof.sh` proves that pvServer delivers the test PVs of both IOCs,
`tools/pv-proof.sh --help` explains it. Where the code comes from and what was
removed from the boilerplate: [UPSTREAM.md](UPSTREAM.md).
