# mist2-ioc:dev - EPICS base, asyn, StreamDevice and the MIST-2 IOC application.
#
# Build from the repository root (the build context):
#   docker build -f emulation/docker/ioc.Dockerfile -t mist2-ioc:dev .
# or `make -C emulation build`. The context is filtered by ioc.Dockerfile.dockerignore.

ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}

# Pinned release tags (from `git ls-remote --tags` on 2026-11-21). asyn and StreamDevice are the
# latest releases. Base is R7.0.10, not the latest R7.0.11: R7.0.11 added a generic rule for
# dbd dependency files that breaks the build of StreamDevice 2.8.26 (its src/Makefile has
# space-indented recipes, "No input files for ../O.Common/stream.dbd"). StreamDevice fixed this
# on master (commit f473f4d), not yet in a release. Move to R7.0.11 with the next StreamDevice.
ARG EPICS_BASE_TAG=R7.0.10
ARG ASYN_TAG=R4-46
ARG STREAM_TAG=2.8.26

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential perl git ca-certificates libreadline-dev libtirpc-dev \
    && rm -rf /var/lib/apt/lists/*

ENV EPICS_HOST_ARCH=linux-x86_64 \
    EPICS_BASE=/opt/epics/base \
    SUPPORT=/opt/epics/support
ENV PATH=${EPICS_BASE}/bin/${EPICS_HOST_ARCH}:${PATH}

# EPICS base
RUN git clone --depth 1 --branch ${EPICS_BASE_TAG} --recurse-submodules --shallow-submodules \
        https://github.com/epics-base/epics-base.git ${EPICS_BASE} \
    && make -C ${EPICS_BASE} -j"$(nproc)" \
    && make -C ${EPICS_BASE} clean

# asyn with its default configuration: no VXI-11, links libtirpc on linux-x86_64
# (configure/CONFIG_SITE.Common.linux-x86_64 of asyn sets TIRPC=YES).
RUN git clone --depth 1 --branch ${ASYN_TAG} https://github.com/epics-modules/asyn.git ${SUPPORT}/asyn \
    && printf 'EPICS_BASE=%s\n' "${EPICS_BASE}" > ${SUPPORT}/asyn/configure/RELEASE \
    && make -C ${SUPPORT}/asyn -j"$(nproc)" \
    && make -C ${SUPPORT}/asyn clean

# StreamDevice, unmodified. No PCRE, no calc: the databases do not use regular expressions
# or the scalcout record. Only the library (src) is built: StreamDevice's example IOC
# (streamApp) registers the VXI-11 driver, which asyn is built without.
RUN git clone --depth 1 --branch ${STREAM_TAG} https://github.com/paulscherrerinstitute/StreamDevice.git ${SUPPORT}/StreamDevice \
    && printf 'EPICS_BASE=%s\nASYN=%s\n' "${EPICS_BASE}" "${SUPPORT}/asyn" > ${SUPPORT}/StreamDevice/configure/RELEASE \
    && make -C ${SUPPORT}/StreamDevice -f Makefile DIRS="configure src" -j"$(nproc)" \
    && make -C ${SUPPORT}/StreamDevice -f Makefile DIRS="configure src" clean

# The repository's EPICS tree at the same relative layout, then the IOC application.
COPY EPICS /opt/mist2/EPICS
RUN make -C /opt/mist2/EPICS/ioc -j"$(nproc)" \
    && make -C /opt/mist2/EPICS/ioc clean

WORKDIR /opt/mist2/EPICS/ioc/iocBoot
ENTRYPOINT ["/opt/mist2/EPICS/ioc/iocBoot/run-ioc.sh"]
CMD ["iocRack", "sim"]
