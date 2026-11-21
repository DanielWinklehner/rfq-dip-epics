# mist2-tools:dev - test and build tools on top of the IOC image (caget, caput, ... included).
#
#   docker build -f emulation/docker/tools.Dockerfile -t mist2-tools:dev emulation/docker
# or `make -C emulation build`. Nothing from the repository is copied: it is mounted at /repo.

ARG IOC_IMAGE=mist2-ioc:dev
FROM ${IOC_IMAGE}

ARG PYEPICS_VERSION=3.5.8

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python-is-python3 \
        python3-pytest python3-yaml python3-docx python3-pil python3-numpy \
        graphviz poppler-utils fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --break-system-packages pyepics==${PYEPICS_VERSION}

# pyepics uses the Channel Access library of the EPICS base in this image.
ENV PYEPICS_LIBCA=${EPICS_BASE}/lib/${EPICS_HOST_ARCH}/libca.so \
    PYTHONUNBUFFERED=1

WORKDIR /repo
ENTRYPOINT []
CMD ["bash"]
