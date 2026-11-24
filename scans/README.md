# mist2scan: one-dimensional scans through Channel Access

A Python program that steps one actuator PV through a list of points and records detector PVs at
each point. It is a Channel Access client and nothing else: it talks to no device, it writes one
PV (the actuator's set point), and only within the limits. Its first use is the dipole scan that
replaces the LabVIEW program (plan/controls.yaml, WP11); the emittance scanners (WP12) are to use
the same program. Design, every key of a definition, the file format and what happens at each
failure: [../docs/emulation/SCAN.md](../docs/emulation/SCAN.md).

| Path | What it is |
|---|---|
| `mist2scan/definition.py` | The definition file: keys (unknown keys are errors), points, part steps (no EPICS import) |
| `mist2scan/stats.py` | Time-weighted statistics of one dwell (no EPICS import) |
| `mist2scan/engine.py` | The scan: refusals, one point, every end, exit codes (no EPICS import) |
| `mist2scan/files.py` | `points.csv`, `scan.json`, `definition.yaml` of one scan |
| `mist2scan/ca.py` | The Channel Access side (pyepics): monitors, fresh reads, control limits, the one write |
| `config/dipole.yaml` | The dipole scan: the plan's proposed PV names, every number ASSUMED |
| `config/emulation-extraction.yaml` | A scan in the full emulation with the plant model: ion source voltage against the Faraday cup current |
| `tests/` | Unit tests with a fake Channel Access side and a fake clock |

Needs Python 3.8 or later, PyYAML and pyepics. Tested on Python 3.10 (WSL host) and 3.12 (the
tools image); 3.8 is the oldest version the code is written for, not run.

```
python -m mist2scan check config/dipole.yaml          # in scans/: connects, prints the plan, writes nothing
python -m mist2scan run config/dipole.yaml            # the scan; ctrl-c ends it cleanly
python -m mist2scan run config/dipole.yaml --start 10 --stop 20 --step 0.25 --dwell 2 --output /data/scans
```

Each scan writes one directory `<output>/<name>-<YYYYmmdd-HHMMSS>/` with `points.csv` (one row
per point, on disk as soon as the point is done), `scan.json` (how it ran and how it ended) and
`definition.yaml` (the definition as it ran: `run` on it repeats the scan). Exit codes: 0
completed, 2 definition error, 3 refused, 4 condition lost, 5 actuator lost, 6 required detector
lost, 7 not settled, 8 program error, 130 ctrl-c, 143 SIGTERM.

Read the table elsewhere:

```python
import pandas; t = pandas.read_csv("points.csv")
import numpy; t = numpy.genfromtxt("points.csv", delimiter=",", names=True, dtype=None, encoding="utf-8")
```

## Tests

| Command | What it proves | Time |
|---|---|---|
| `python3 -m unittest discover -s scans/tests -t scans` (repository root) | Points, part steps, settling, statistics, invalid and missing values, every end with the actuator's writes, refusals, rows on disk after an abort, unknown keys | 1 s |
| `emulation/devtest/run.sh emulation/devtest/scan` | The program against soft records in an IOC, run as `python -m mist2scan run`: three peaks found where the database puts them, missing values exactly where a detector was INVALID, a condition lost, ctrl-c and SIGTERM, an IOC restart, refusals | about 3 min |

In the tools image:

```bash
docker run --rm -v "$PWD":/repo -w /repo -u "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1 mist2-tools:dev python3 -m unittest discover -s scans/tests -t scans
```

## In the emulation

The tools container has pyepics and reaches both IOCs (`docs/emulation/README.md`, section 3).
With the emulation and the plant model up (`make -C emulation up-plant`) and the source running
(SCAN.md, section 7):

```bash
docker compose -f emulation/compose.yaml --profile tools run --rm -T -e PYTHONPATH=/repo/scans tools \
    python -m mist2scan run scans/config/emulation-extraction.yaml --output emulation/build/scans
```

## On the lab computer (Ubuntu; NOT VERIFIED there)

The owner said (2026-11-24) that the lab computer runs Ubuntu; the version is not known. These
steps leave the system Python alone: pyepics and PyYAML go into a virtual environment. The scan
is a program a person starts, not a service: no unit file.

```bash
sudo apt install python3-venv git
git clone -b emulated-iocs https://github.com/DanielWinklehner/rfq-dip-epics.git ~/rfq-dip-epics
python3 -m venv ~/venv-mist2scan
~/venv-mist2scan/bin/pip install pyepics==3.5.8 PyYAML
cd ~/rfq-dip-epics && ~/venv-mist2scan/bin/python -m unittest discover -s scans/tests -t scans
cd ~/rfq-dip-epics/scans
export EPICS_CA_AUTO_ADDR_LIST=NO EPICS_CA_ADDR_LIST="<the IOC hosts>"
~/venv-mist2scan/bin/python -m mist2scan check config/dipole.yaml
```

The clone location and the venv path are proposals. `EPICS_CA_ADDR_LIST` must reach the IOCs
that serve the dipole supplies and the picoammeter (T24, T25; on the lab computer itself
`127.0.0.1`); which addresses that are is not settled. pyepics 3.5.8 is the version the emulation
uses; whether it installs on that computer's Python is not known until it is tried.
