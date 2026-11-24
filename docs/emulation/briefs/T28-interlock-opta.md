You are an implementation engineer on the MIST-2 ion source control system (EPICS). You have one task, T28: the lab's old interlock box (an Arduino Mega that read the two door switches of the HV cage) was not found after the move. The owner decided on 2026-11-24 that an Arduino Opta takes its place. Write the firmware for it, with a reproducible way to compile it, and prove as much of it as can be proven without hardware. No hardware is available to you or to the lead.

FIRST LINE OF YOUR FINAL REPORT must be: `MODEL: <the exact model ID you are running as>`.

# Setup
- Your git worktree is `/home/daniel/code/rfq-dip-epics/.claude/worktrees/t28`, on branch `emu/t28-interlock-opta`, already created from `emulated-iocs`. Work ONLY there: change into it first and use paths inside it for every file you read or write. Never touch the main checkout or another worktree.
- Commit on that branch only. Small commits with clear messages, each ending with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never open a pull request.
- Host: WSL2 Ubuntu 22.04 with g++ 11 and Python 3.10. `sudo` needs a password, so install nothing on the host. Docker works without sudo. Python tooling runs in the image `mist2-tools:dev`, the IOC in `mist2-ioc:dev`.
- The full emulation (`make -C emulation up`, `make -C emulation test`) exists once on this machine: you do not need it and must not start it. A device case (`emulation/devtest/run.sh <case>`) is its own Compose project and needs no lock.
- Long commands may exceed your tool's time limit: run anything that takes longer than a minute in the background, write output and exit code to files, and look at the files in short steps.
- Your shell's working directory may reset between commands: start every command with `cd /home/daniel/code/rfq-dip-epics/.claude/worktrees/t28 && ...`.
- Some file tools refuse `.db` files as binary: read them with `cat`.
- Never run `rm` with a shell variable in its path. Never pipe a download into a shell (`curl ... | sh`): fetch a release archive, check its checksum, unpack it. Leave no container and no process running when you finish.
- The owner's name, e-mail address and project name go into no request to an outside service.

# Read first
1. `AVR/libcom1/README.md` (all of it), `AVR/libcom1/examples/EthernetExample/EthernetExample.ino` (an Opta sketch that was compiled and never run), `AVR/libcom1/tests/Makefile` and `tests/script.hpp` (how the library is tested on a PC).
2. `AVR/devices/InterlockBox/InterlockBox.ino`: the old box. Its channel map and what it does with its outputs by itself are the model. `AVR/devices/SolenoidValveBox/SolenoidValveBox/SolenoidValveBox.ino`: the sketch that was flashed and seen to work with the IOC on 2026-11-24.
3. `EPICS/Db/interlockbox.db` (use `cat`), `EPICS/Db/libcom1_device.db`, the commands of `EPICS/Db/libcom1.proto` they use, and the block of port AVR11 in `EPICS/ioc/iocBoot/iocRack/ports.real.cmd` and `ports.sim.cmd`.
4. `emulation/sim/config/rack.yaml`, entry `interlockbox`; `emulation/sim/mist2sim/devices/libcom1.py` (the simulator's engine, `number_format`), `emulation/sim/tools/libcom1_replay.py` and `emulation/sim/run_tests.sh` (how the simulator's engine is compared with the C++ library, line by line).
5. `emulation/devtest/libcom1_devices` (the device case that holds the interlock box), `emulation/devtest/run.sh` (header).
6. `docs/emulation/STATUS.md`: answers 27, 53 and question 21; `plan/controls.yaml`: the devices `ilk_old` and `ilk_new` and the section `interlock`.
7. `reference/lab-2026/AVR/devices/FlowMeters/FlowMeters.ino`: the lab's own Opta sketch (older libcom1, USB serial), which ran on an Opta.

# Decided by the lead (do not change; if one cannot be built as written, stop and report)
D1. **Transport:** USB serial (`Serial`), as the old box and the lab's two Optas in use. The IOC opens it as a serial port at 115200 8N1 and nothing in the IOC's files changes. Ethernet comes later with the network plan: keep the two transport functions in one place of the sketch.
D2. **Channel map, in this order: i1, i2, s1, s2,** as the old box, so `interlockbox.db` stays as it is and no PV is renamed. i1, i2: the door inputs, 1 = door closed, 0 = open; a set is accepted and does nothing, as in the old box. s1, s2: two relays switched by command (1 = on, anything else off) and read back, as in the old box. No database uses them.
D3. **Terminals:** input I1 is i1, input I2 is i2. Relays 1 and 2 are the interlock outputs. Relays 3 and 4 are s1 and s2.
D4. **The interlock outputs are decided in the Opta, without the IOC:** relays 1 and 2 are on only while both doors are reported closed. Nothing received over the line can switch them. They are off after power-on and after a restart.
D5. **A door counts as closed when its input is high** (the switch closes when the door closes and feeds the input from the Opta's own supply, so a broken wire reads as an open door). ASSUMED: the owner has not yet said which way the switches work. One named constant per input for the level; say in the README why the other choice is not fail-safe.
D6. **Hold time:** when an input reads open, that door is reported open, and the interlock relays are off, until the input has read closed without interruption for `HOLD_MS` (one named constant, 1000). Reason: the IOC reads the box ten times a second and latches the supplies off when it sees an open door; a shorter opening or a bouncing switch must reach it. After power-on both doors are reported open until the hold time has passed.
D7. **No latch in the Opta:** the relays come back on when both doors are closed again (after the hold time), as the old box's outputs did. The IOC latches the supplies. Whether the hardware contact must latch is a question for the owner (plan, section `interlock`): put it under QUESTIONS, build nothing for it.
D8. **Watchdog:** a hardware watchdog of the Opta's processor, started in `setup()` and served in `loop()`, so that a sketch that hangs with the relays on is restarted (relays off). One named constant for the time, 0 = no watchdog. Find the API in the installed core's own sources and name the file. Say what happens on the board during a flash and while no computer has the port open, as far as the sources tell; what they do not tell goes under NOT VERIFIED.
D9. **No communication timeout** (`set_comm_timeout`): the interlock does not depend on the IOC.
D10. **Identity** `InterlockOpta`, firmware `__DATE__`.
D11. **Lamps:** the four status LEDs over the relays follow their relays, if the board lets a sketch drive them. One more lamp for "both doors closed" and one for "a door open" if the board has them. Take every pin name from the installed core's variant files and name the file; a lamp the RS-485 variant of the Opta (not Lite, not WiFi, sold as AFX00001: check that number) does not have is left out.

# What to build
R1. **The sketch** `AVR/devices/InterlockOpta/InterlockOpta.ino`, with everything that does not touch the board in headers beside it, so that it compiles on a PC: the decision of D4 to D6 as a small class or set of functions that gets the two input levels and the time in milliseconds and gives the reported doors and the relay states (no `millis()`, no pins inside), and the device with its channel map on top of it. The `.ino` holds pins, `Serial`, the watchdog and the lamps and nothing else that could be tested. Arithmetic on `millis()` must survive its wrap after 49 days. No dynamic memory, no blocking wait in `loop()`.
R2. **A reproducible compile:** `AVR/tools/arduino.Dockerfile` for an image `mist2-arduino:dev` with `arduino-cli` (a named release, fetched as a release archive with its checksum checked) and the cores `arduino:avr` and the Opta's Mbed core, both at named versions; and `AVR/tools/compile.sh <sketch directory> <fqbn>`, which builds the image if it is missing and compiles the sketch in a container with the libraries `AVR/libcom1` and `AVR/libutil` of the checkout (not copies), prints the size, and exits with the compiler's code. Warnings of the sketch's own files and of libcom1 are shown; the sketch and its headers compile without one. A short `AVR/tools/README.md`.
   If the core cannot be fetched from this machine, stop and report: do not replace the compile by a guess.
R3. **The two sketches of the Arduino Mega still compile with the same tool** (`AVR/devices/InterlockBox`, `AVR/devices/SolenoidValveBox/SolenoidValveBox`, board Arduino Mega 2560), unchanged. `AVR/libcom1` and `AVR/libutil` are not yours: if the Opta's compiler rejects or warns about something in them, stop at that point and report it with the message.
R4. **Tests on the PC** in `AVR/devices/InterlockOpta/tests` (a Makefile, `make` runs them, g++ with the flags of the library's own tests):
   a. The decision: power-on, both closed after the hold time, each door alone open, an opening of one millisecond, a bouncing closing, the wrap of the millisecond counter in the middle of a hold, an opening exactly at the end of the hold.
   b. The device through the library, as a conversation of lines in and lines out: identity, the channel list, query-all in the order of D2, a set of s1 and s2 with read-back, a set of i1 (accepted, nothing changes), and that no line whatsoever changes relays 1 and 2 (try the commands of the README against every channel name and against names that do not exist).
   c. **The simulator's entry agrees with the firmware:** the same lines sent to the PC build of the device and to the simulator's engine built from the entry `interlockbox` of `emulation/sim/config/rack.yaml` give the same replies, line by line, with the doors in the same states. Model: `emulation/sim/tools/libcom1_replay.py`.
R5. **The emulation follows the firmware:** the entry `interlockbox` in `emulation/sim/config/rack.yaml` and its copy in `emulation/devtest/libcom1_devices` (identity, number format, comment), and what the case's test expects of it. No PV, no record and no port changes.
R6. **`AVR/devices/InterlockOpta/README.md`,** for the owner, who flashes with the Arduino IDE (version 2, on Windows 11 or on Ubuntu 26.04): what the box does (D2 to D8, in plain words), the terminals with a wiring table (supply, the two switches, the two interlock contacts, the two spare relays), the electrical limits that matter for it (supply voltage, what an input accepts and from which voltage it reads high, what a relay contact may switch) each with the page of Arduino's documentation or data sheet it comes from, the flashing steps (the board package's name as the IDE shows it, the board, the libraries of this repository in the sketchbook), a first check with the serial monitor (the lines to type and what must come back), the constants, and a table "verified here / not verified". Anything you could not read in a source you can name is written as not known, not as a number.
   Fetch the documentation with your own web tools. A page you cannot read is named as not read.

# Tests
1. The compile for the Opta, exit code 0, with the sizes. See it fail once (a syntax error in a header), exit code not 0.
2. The two Mega sketches with the same tool, exit code 0.
3. `make` in `AVR/devices/InterlockOpta/tests`: every test of R4. See each property fail once without it: say for a, b and c which line you changed and what the test printed.
4. `make -C AVR/libcom1/tests`, `emulation/sim/run_tests.sh`, the device case `emulation/devtest/libcom1_devices`, `make -C emulation plan-check`: still pass.

# Files you own
`AVR/devices/InterlockOpta/**`, `AVR/tools/**`, the entry `interlockbox` of `emulation/sim/config/rack.yaml`, the interlock box's part of `emulation/devtest/libcom1_devices/**`, a new tool under `emulation/sim/tools/` if R4 c needs one. Not yours: `AVR/libcom1`, `AVR/libutil`, the other sketches, `EPICS/**`, `plan/controls.yaml`, the registry, the simulator's core, `emulation/tests`, `docs/emulation/STATUS.md`, `PLAN.md`, `README.md`, `LAB-SETUP.md`, the udev rule files. If you find you need a change there, stop at that point and report it with the reason.

# Acceptance (the lead runs these from your worktree)
    AVR/tools/compile.sh AVR/devices/InterlockOpta <the Opta's fqbn>
    AVR/tools/compile.sh AVR/devices/InterlockBox arduino:avr:mega
    AVR/tools/compile.sh AVR/devices/SolenoidValveBox/SolenoidValveBox arduino:avr:mega
    make -C AVR/devices/InterlockOpta/tests
    make -C AVR/libcom1/tests
    emulation/sim/run_tests.sh
    emulation/devtest/run.sh emulation/devtest/libcom1_devices
    make -C emulation plan-check
All exit 0. The lead then runs the system tests of the full emulation on the merged branch.

# Rules
- Do not invent facts about the board: a pin name, a voltage, a current, an API call each come from a source you name (a file of the installed core with its path, a page of the documentation with its address). What you assume is marked ASSUMED where it stands.
- This box is not personnel protection and the README says so in its first paragraph: the door switches have to break the supplies' own interlock input or their mains for that (plan, section `interlock`, layer A).
- No change of behaviour beyond this task. If something here turns out wrong or cannot be built as described, stop and say so in the report instead of building something else.
- A report that says "done" is not evidence: give the commands you ran, their exit codes and the numbers they printed, and say plainly what you did not do or could not show.

# Final report, with these headings
MODEL, BRANCH, BUILT, THE BOARD (every fact with its source), VERIFIED (commands, exit codes, times, how each test was seen to fail), DECISIONS (yours, with reasons), ASSUMED, NOT VERIFIED, QUESTIONS FOR THE OWNER, NEEDS THE LEAD (text for STATUS.md, for the plan, for LAB-SETUP.md and for the udev rule), COMMITS.
