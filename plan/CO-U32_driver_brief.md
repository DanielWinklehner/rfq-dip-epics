# Project brief: Matsusada CO-U32 on Linux and Windows

Use this as the first prompt (or as `CLAUDE.md`) of a separate Claude Code project. Run it on a machine that has the CO-U32 plugged in. Without the hardware nothing here can be tested.

## Goal

Run the rack IOC on Linux. The only thing that keeps it on Windows today is the vendor driver for the Matsusada CO-U32 (USB to optical adapter for the AU high-voltage supplies). The result must work on Linux and Windows with the same EPICS configuration.

## What is known

- On the Windows IOC the adapter shows up as a serial port (COM9, 9600 baud, 8N1, no flow control). asyn opens it with `drvAsynSerialPortConfigure`. See `EPICS/st.cmd` in `github.com/DanielWinklehner/rfq-dip-epics`.
- The protocol on top is plain ASCII, terminated by CR, and already implemented in `EPICS/Db/matsusada_co_ctrl.proto`:
  - `#<unit> CH0 <4 hex digits>` sets the voltage, `#<unit> CH0?` answers `CH0=<hex>H`
  - `#<unit> MN1` answers `MONI1=<hex>H` (voltage monitor), `MN2` the current monitor
  - Manual: "CO series" digital controller manual from Matsusada (the protocol file links a copy).
- So no protocol work is needed. The task is only: get a serial byte stream to the adapter on Linux.

- A second adapter of a newer type, the Matsusada USB-OPT, will drive a second optical chain. Everything below applies to it as well. It may use a different USB chip than the CO-U32, so identify both.

## What is not known (find out first, before writing any code)

1. USB vendor ID and product ID of the CO-U32.
   - Windows: Device Manager, the COM port, Details, "Hardware Ids".
   - Linux or WSL (with `usbipd attach`): `lsusb -v`.
2. Which chip is inside. Clues: the driver files the Matsusada installer puts on Windows (`ftdibus.sys`/`ftser2k.sys` means FTDI, `silabser.sys` means Silicon Labs CP210x, `usbser.sys` means standard CDC-ACM), and the descriptor strings from `lsusb -v`.

## Decision tree

| Finding | Work needed |
|---|---|
| Standard CDC-ACM device | None. Linux creates `/dev/ttyACM*`. Add a udev rule for a stable name |
| FTDI, CP210x or similar with a Matsusada-specific ID | No driver. Bind the stock kernel driver to the ID (`new_id`) with a udev rule. Deliver the rule and an install script |
| Custom USB protocol | Small user-space bridge on libusb (works on Linux and Windows) that exposes a pseudo terminal or a TCP port, so that asyn and the protocol file stay unchanged. Capture the Windows traffic with USBPcap/Wireshark to learn the framing |

The Matsusada CO-E32 is the LAN version of the same adapter and needs no driver at all (`drvAsynIPPortConfigure`). It may replace the CO-U32 later, but its delivery time rules it out before the winter break, so this project is on the critical path for the Linux IOC.

## Deliverables

- `README` with the findings (IDs, chip, what Linux does out of the box).
- udev rule that gives the adapter a fixed name, for example `/dev/matsusada-co`, independent of the plug order.
- If needed: the bridge, as a service (systemd unit on Linux, a documented way to start it on Windows).
- `st.cmd` snippet for Linux and a test script that reads `CH0?`, `MN1` and `MN2` from one unit and compares with the front panel.
- A short test report.

## Rules for testing

- These are 20 kV supplies. Develop with read-only queries (`CH0?`, `MN1`, `MN2`, status). Send set commands only with the output disabled and the HV interlock open, and only after the read path works.
- Do not modify the Windows installation of the production IOC. Use a second PC or a Linux live system for the experiments.
- Acceptance: one hour of polling at 10 Hz from a Linux IOC without a single timeout or mismatch, unplug and replug recovers without restarting the IOC.
