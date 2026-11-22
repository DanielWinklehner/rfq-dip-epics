# mist2loop: the control loops of MIST-2

A Python service that runs the PID of each control loop. The loop's records (mode, set point,
gains, limits, state) are plain records in the platform IOC, `iocHV` (`EPICS/Db/loop.db`); the
service knows a loop only by their prefix and talks to them over Channel Access. The records
also hold the loop safe without the service. Design, PV table, hand-back rules, settings and
tuning: [../docs/emulation/LOOP.md](../docs/emulation/LOOP.md).

| Path | What it is |
|---|---|
| `mist2loop/pid.py` | The algorithm, without EPICS: state and inputs in, output and new state out |
| `mist2loop/loop.py` | One loop: checks, hand-back, refusal, bumpless start (no EPICS import) |
| `mist2loop/service.py` | The Channel Access side: monitors, writes, the cycle (pyepics) |
| `config/mist2.yaml` | The loops it runs (prefixes) and the period. The same file in the emulation and on the platform computer |
| `tests/test_pid.py` | The algorithm alone: `python3 -m unittest discover -s loops/tests -t loops` from the repository root |
| `tests/test_loop.py` | The loop's logic with a fake Channel Access side (start, refusal, bumpless start, hand-back order, counting), the same command |
| `systemd/mist2loop.service` | The unit for the platform computer |

Needs Python 3.8 or later (Ubuntu 20.04 has 3.8, 22.04 3.10, 24.04 3.12), PyYAML and pyepics.
The unit tests ran on Python 3.10 (WSL host) and 3.12 (the tools image); 3.8 is the oldest
version the code is written for (no newer syntax or library features) but was not run.
pyepics brings its own Channel Access library, so EPICS base is not needed for the service.

```
python -m mist2loop --config config/mist2.yaml     # in loops/
```

It starts whether or not the IOC runs and connects when the IOC appears; it logs one line per
event (connection, mode changes with their reason, a failing cycle once), not one per cycle; it
counts `_count` only for a completed cycle, so the IOC's watchdog also catches a service whose
cycles fail; SIGTERM or ctrl-c ends it
with every loop in MANUAL.

## In the emulation

The Compose service `loop` (container `mist2emu-loop-1`, 172.30.0.40, image `mist2-tools:dev`)
starts and stops with the rest (`make -C emulation up`, `down`). Its log:
`docker logs mist2emu-loop-1`.

## On the platform computer (Ubuntu, a light variant; NOT VERIFIED there)

The owner said (2026-11-22) that the mini PC runs one of the light Ubuntu variants; which one
and which version is not known. These steps leave the system Python alone: pyepics and PyYAML go
into a virtual environment.

```bash
sudo apt install python3-venv git                    # Python from the distribution
sudo useradd --system --create-home mist2            # if the IOC does not have its own user yet
sudo mkdir -p /opt/mist2 && sudo chown mist2: /opt/mist2
sudo -u mist2 git clone https://github.com/DanielWinklehner/rfq-dip-epics.git /opt/mist2/rfq-dip-epics
sudo -u mist2 python3 -m venv /opt/mist2/venv-mist2loop
sudo -u mist2 /opt/mist2/venv-mist2loop/bin/pip install pyepics==3.5.8 PyYAML
sudo -u mist2 sh -c 'cd /opt/mist2/rfq-dip-epics && /opt/mist2/venv-mist2loop/bin/python -m unittest discover -s loops/tests -t loops'
sudo cp /opt/mist2/rfq-dip-epics/loops/systemd/mist2loop.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mist2loop
journalctl -u mist2loop -f                           # its log
```

The paths, the user `mist2` and the clone location are proposals; adapt the unit file if the IOC
lives elsewhere. pyepics 3.5.8 is the version the emulation uses; whether it installs on the
computer's Python is not known until it is tried (3.8 or later is needed).

Channel Access: the service is a client only, and all its records are in `iocHV` on the same
computer, so the unit sets `EPICS_CA_ADDR_LIST=127.0.0.1`. A client alone has none of the
trouble of two servers on one host. Check after the start that `LOOP-DIS:service:get` reads 1
from the control room.
