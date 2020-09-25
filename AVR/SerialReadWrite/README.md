# RERL (Read-Eval-Respond-Loop)

RERL is a modification for the REPL computing environment, but instead of
being interactive for a programmer, it is meant to be interactive as a shell.

Like any shell, commands can be submitted for evaluation.

## Current Commands:

- GD?\<pin\>
  * Get Digital Pin
  * Pin is the pin number of the Arduino

- SD!\<pin\>:\<bool\>
  * Set Digital Pin
  * Pin is the pin number on Arduino
  * Digital IO pins can be set to HIGH or LOW

## Make and Compile:

You will need to have installed:
- AVR Toolchain (avr-gcc, avr-binutils, etc.)
- avrdude
- avr-libc
- CMake

Start by making a new folder to build. We'll call our folder "build" and go into
it.
```
mkdir build && cd build
```

Run CMake on the parent directory. Be sure to specify PROG_TYPE, USBPORT, MCU, F_CPU, and BAUD, if need be, using the -D flags.
By default the values are as follows: PROG_TYPE = "wiring", USBPORT = "/dev/ttyACM0", MCU = "atmega2560", F_CPU = "16000000", BAUD = "19200"
```
cmake ..
```

To flash program onto MCU, run
```
make flash
```

(Untested on Windows)

Output Files:
- *.elf
  * Linked executable binary 
- *.hex
  * Intel Hex File to be programmed onto MCU
- *.lst
  * Disassembly of the program
  
## Local Emulation Environment
You can run the ELF file in QEMU, a local emulator, so you don't need to keep
reflashing the AVR. Unfortunately, QEMU will use up as many resources as you
give it, so we will also need to employ cpulimit to reduce the execution speed
to what would be considered normal. In the build directory, run:
```
cpulimit -l <percent> qemu-system-avr -machine <MCU> -serial tcp::<port>,server,nowait -nographic -bios <executable>
```
where,
- \<percent\> refers to the CPU utilization to give to QEMU (try 3). You can get
a lower and upper bound by reading the output from `cpulimit -h`
- \<MCU\> refers to the MCU to emulate. A list can be found at 
https://www.qemu.org/docs/master/system/target-avr.html
- \<port\> refers to the port to use when redirecting the Serial I/O 
(I used 5678)
- <executable\> refers to the ELF file to use when running QEMU

Afterwards, a Serial I/O channel can be opened by running
```
telnet localhost <port>
```
where,
- \<port\> is the same as the one specified above.

Quit QEMU by typing `q [Enter]` and telnet by `[Ctrl]+] [Ctrl]+d`


## Tested Environments:
- Compile Time:
  * Ubuntu Linux 18.04, kernel 5.4.0
  * Manjaro Linux, kernel 5.4.64
  * avr-gcc 10.2.0
  * avr-gcc 5.4.0
  * avr-libc 2.0.0
  * CMake 3.10.2
  * CMake 3.18.2
- Runtime:
  * Arduino Mega 2560
  * QEMU AVR Emulator

## Notes:

TODO/Suggestions:
- Doxygen doc support
- Make interface compatibility to that of the Communication library
- Test cases, CI/CD
- Test Windows compatibility
- Confirm minimal heap allocations to reduce heap fragmentation and reduce the 
chance of a stack crash
- Watchdog implementation to restart on unrecoverable code failure
- Error Correcting Codes for communication: Currently looking into Turbo, LDPC, Reed–Solomon, and Golay 
- EtherCAT communication
