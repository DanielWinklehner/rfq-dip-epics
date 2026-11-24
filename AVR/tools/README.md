# AVR/tools

Compile the sketches of this repository without an Arduino IDE, in a container. Nothing is
uploaded: this is for checking that a sketch builds, and how large it is.

    AVR/tools/compile.sh <sketch directory> <fqbn>

    AVR/tools/compile.sh AVR/devices/InterlockOpta arduino:mbed_opta:opta
    AVR/tools/compile.sh AVR/devices/InterlockBox arduino:avr:mega
    AVR/tools/compile.sh AVR/devices/SolenoidValveBox/SolenoidValveBox arduino:avr:mega

- Builds the image `mist2-arduino:dev` from `arduino.Dockerfile` the first time (about a minute,
  downloads about 170 MB), then compiles in a throw-away container without network, as the
  calling user, with the checkout mounted read-only.
- Libraries: `AVR/libcom1` and `AVR/libutil` of the checkout, passed with `--library` (no copies).
- `--warnings all` (`-Wall -Wextra`): warnings of the sketch, its headers, the libraries and the
  core are printed. The sizes are printed at the end ("Sketch uses ... bytes").
- Exit code: that of `arduino-cli compile` (0 = compiled), 2 for wrong arguments, 3 when the
  image could not be built.
- Needs Docker only. The image holds Debian 12 (pinned by digest), arduino-cli 1.5.1 (the release
  archive, its SHA-256 checked against the release's checksum file) and the cores
  `arduino:avr@1.8.8` and `arduino:mbed_opta@4.6.0` (each archive checked by arduino-cli against
  Arduino's package index). Rebuild after changing a version:
  `docker build -t mist2-arduino:dev -f AVR/tools/arduino.Dockerfile AVR/tools`.

arduino-cli, and with it the Arduino IDE 2, refuses a library whose examples contain a link
loop ("directories symlink loop detected"). `AVR/libcom1/examples/StandaloneExample` held such
links until 2026-11-25; they are gone, and its build file names the directories instead.

To read the core's sources (pin names, APIs), copy them out of the image:

    docker run --rm -u "$(id -u):$(id -g)" -v "$PWD/core:/out" mist2-arduino:dev \
        cp -r /opt/arduino/data/packages/arduino/hardware/mbed_opta/4.6.0 /out/
