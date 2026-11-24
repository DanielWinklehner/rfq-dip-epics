# mist2daq: the dipole supplies' NI box as a libcom1 device

The dipole magnet supplies have an analog interface only (plan: "analog 0-10 V") and hang on an
NI USB-6001 at the lab computer. `mist2daq` is a small Python service that owns that box and
serves its channels as a libcom1 protocol 2 device over TCP (`AVR/libcom1/README.md`), so the IOC
reads and sets them with the unmodified `EPICS/Db/libcom1.proto`, like an Arduino Opta. Records:
`EPICS/Db/dipole.db`. Design, every configuration key, the behaviour at start, stop, lost client
and wrong input, and the table of unknowns: [../docs/emulation/DAQ.md](../docs/emulation/DAQ.md).

**It writes nothing by itself**: no output at its start, at a lost client or at its stop. An
output's value is "not known" (`nan`) until the first set of this run.

| Path | What it is |
|---|---|
| `mist2daq/protocol.py` | libcom1 protocol 2, device side, no I/O (proven against the real library) |
| `mist2daq/config.py` | The configuration file, checked completely before anything is opened |
| `mist2daq/backends.py` | `sim` (in memory, a monitor following an output with a lag) and `nidaqmx` (NOT VERIFIED) |
| `mist2daq/service.py` | Scaling, limits, held values, the communication timeout; the TCP server and the status port |
| `config/dipole.yaml` | The lab computer's file: every machine value in it is ASSUMED |
| `systemd/mist2daq.service` | The unit for the lab computer |
| `tests/` | Unit tests: `python3 -m unittest discover -s daq/tests -t daq` from the repository root |
| `tools/compare_libcom1.sh` | The protocol against the real library (`AVR/libcom1`, needs g++) |

Needs Python 3.8 or later and PyYAML; the `nidaqmx` backend also needs NI's package `nidaqmx`
(version 1.7.0 requires Python 3.9 or later) and NI's driver NI-DAQmx. The unit tests ran on
Python 3.12 (image `mist2-tools:dev`); 3.8 is what the code is written for but was not run.

```
docker run --rm --network none -v "$PWD":/repo -w /repo --entrypoint python3 mist2-tools:dev \
    -m unittest discover -s daq/tests -t daq           # from the repository root
python -m mist2daq --config config/dipole.yaml          # in daq/
python -m mist2daq --config config/dipole.yaml --check  # check the file and open the box, write nothing
echo '{"cmd": "status"}' | nc -q1 127.0.0.1 5101        # what it holds, wrote and received
```

## On the lab computer (Ubuntu; NOT VERIFIED there)

**First question, before anything else**: does NI's driver serve the USB-6001 on this computer?
NI's Linux documentation that could be read does not list the USB-6001 (docs/emulation/DAQ.md,
"NI on Linux"). If LabVIEW drives the box under Ubuntu today, NI-DAQmx is already there and works
with it: check with `python -m nidaqmx` below. If not, stop here and see DAQ.md for the options.

```bash
sudo apt install python3-venv git
sudo useradd --system --create-home mist2            # if it does not exist yet
sudo mkdir -p /opt/mist2 && sudo chown mist2: /opt/mist2
sudo -u mist2 git clone -b emulated-iocs https://github.com/DanielWinklehner/rfq-dip-epics.git /opt/mist2/rfq-dip-epics
sudo -u mist2 python3 -m venv /opt/mist2/venv-mist2daq
sudo -u mist2 /opt/mist2/venv-mist2daq/bin/pip install PyYAML nidaqmx
# NI's driver, if it is not installed yet: NI's package offers to install it (needs sudo):
#   sudo /opt/mist2/venv-mist2daq/bin/python -m nidaqmx installdriver
# Whether the user mist2 needs a group or a udev rule to open the box is not known: if --check
# below fails with a permission error, that is the place to look.
sudo -u mist2 sh -c 'cd /opt/mist2/rfq-dip-epics && /opt/mist2/venv-mist2daq/bin/python -m unittest discover -s daq/tests -t daq'
```

Then the configuration: `daq/config/dipole.yaml`. Every value marked ASSUMED is a placeholder:
the device name NI-DAQmx gives the box, which output and which input are wired, amperes per volt
in both directions, the offset, the current range, the terminal configuration of the input, and
where the IOC connects from. Copy the file (e.g. `config/dipole.local.yaml`) if the clone is
updated with git, and point the unit at the copy.

```bash
cd /opt/mist2/rfq-dip-epics/daq
sudo -u mist2 /opt/mist2/venv-mist2daq/bin/python -m mist2daq --config config/dipole.yaml --check
```

`--check` reads the configuration, finds the box (`device`, `product_type`) and opens the input
task, then closes it. It writes no output.

### With a voltmeter, before a supply is connected

The supply stays disconnected from the NI box. A voltmeter on the analog output (`ao0` against
`AO GND`), a wire from that output to the analog input of the configuration (`ai0` against
`AI GND` for RSE), so that the read-back has something to read.

```bash
sudo -u mist2 /opt/mist2/venv-mist2daq/bin/python -m mist2daq --config config/dipole.yaml &
# The voltmeter shows what the box had before: the service wrote nothing.
printf 'I\nA\n' | nc -q1 127.0.0.1 5100        # oID=DipoleDAQ;...;CH=o1,i1   and   onan:<monitor>
printf 'So110\n' | nc -q1 127.0.0.1 5100        # ok: 10 A at 10 A/V (ASSUMED) = 1.000 V on the meter
printf 'A\n' | nc -q1 127.0.0.1 5100            # o10:10 with the wire from ao0 to ai0
printf 'So1500\n' | nc -q1 127.0.0.1 5100       # ERR5: outside the limits; the meter stays at 1 V
echo '{"cmd": "status"}' | nc -q1 127.0.0.1 5101
kill %1                                          # the meter stays at what it was? (see DAQ.md: not known)
```

Each `nc` is a new client: it only gets in while no IOC is connected (a second client is refused
while the first one is active, see DAQ.md). Write down what the voltmeter shows after `kill` and
after unplugging the USB cable: these answer two open points.

### The unit

```bash
sudo cp /opt/mist2/rfq-dip-epics/daq/systemd/mist2daq.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mist2daq
journalctl -u mist2daq -f
```

One line per event (a client, a set, a refusal, a failure), none per poll.

### The IOC

Which computer's IOC serves the dipole is not decided (the devices are "later" in the plan). The
lines for its `st.cmd`, with the drive limits equal to the service's limits:

```
drvAsynIPPortConfigure("DIPOLE", "127.0.0.1:5100")
dbLoadRecords("$(MIST2_DB)/dipole.db",         "PORT=DIPOLE,DEVICE=dipole,DRVL=0,DRVH=100")
dbLoadRecords("$(MIST2_DB)/libcom1_device.db", "PORT=DIPOLE,DEVICE=dipole")
dbLoadRecords("$(MIST2_DB)/first_contact.db",  "P=dipole,N=current,REQ=dipole:current:set,RB=dipole:current:held")
```

In the emulation: the device case `emulation/devtest/dipole` (`emulation/devtest/run.sh emulation/devtest/dipole`).
