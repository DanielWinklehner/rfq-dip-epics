# mist2-arduino:dev - arduino-cli and the two Arduino cores this repository compiles for.
#
#   docker build -t mist2-arduino:dev -f AVR/tools/arduino.Dockerfile AVR/tools
#
# AVR/tools/compile.sh builds it when it is missing. Everything is pinned:
#   base image      Debian 12 slim, by digest (pulled 2026-11-24)
#   arduino-cli     a release archive from GitHub, checked against the SHA-256 of the release's
#                   own checksum file (https://github.com/arduino/arduino-cli/releases/tag/v1.5.1,
#                   1.5.1-checksums.txt)
#   cores           arduino:avr (Arduino Mega 2560) and arduino:mbed_opta (Arduino Opta) at named
#                   versions. arduino-cli fetches them from Arduino's package index and checks each
#                   archive against the size and checksum the index lists for it.
#
# The cores live in /opt/arduino (read-only for the user the container runs as). The sketch
# and the libraries are mounted from the checkout at compile time, nothing of the repository
# is copied into the image.

FROM debian@sha256:e67eeead736ff7bbe258ef088bff683635c561b1fcfefad0806c1df4ab49ce0e

ARG ARDUINO_CLI_VERSION=1.5.1
ARG ARDUINO_CLI_SHA256=28a8e119c498a25607821c36cb2dc49e8463941b261a0d99091baa7bc692dd2b
ARG CORE_AVR=arduino:avr@1.8.8
ARG CORE_OPTA=arduino:mbed_opta@4.6.0

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

RUN set -eu; \
    archive="arduino-cli_${ARDUINO_CLI_VERSION}_Linux_64bit.tar.gz"; \
    curl -fsSL -o "/tmp/$archive" \
      "https://github.com/arduino/arduino-cli/releases/download/v${ARDUINO_CLI_VERSION}/$archive"; \
    echo "${ARDUINO_CLI_SHA256}  /tmp/$archive" | sha256sum -c -; \
    mkdir /tmp/cli; \
    tar -xzf "/tmp/$archive" -C /tmp/cli; \
    install -m 0755 /tmp/cli/arduino-cli /usr/local/bin/arduino-cli; \
    rm -rf /tmp/cli "/tmp/$archive"; \
    arduino-cli version

ENV ARDUINO_DIRECTORIES_DATA=/opt/arduino/data \
    ARDUINO_DIRECTORIES_DOWNLOADS=/opt/arduino/staging \
    ARDUINO_DIRECTORIES_USER=/opt/arduino/user \
    ARDUINO_UPDATER_ENABLE_NOTIFICATION=false \
    ARDUINO_METRICS_ENABLED=false

RUN set -eu; \
    arduino-cli core update-index; \
    arduino-cli core install "$CORE_AVR"; \
    arduino-cli core install "$CORE_OPTA"; \
    arduino-cli core list; \
    rm -rf /opt/arduino/staging; \
    mkdir -p /opt/arduino/user; \
    chmod -R a+rX /opt/arduino

# compile.sh runs the container as the calling user, who has no home directory in the image
ENV HOME=/tmp
