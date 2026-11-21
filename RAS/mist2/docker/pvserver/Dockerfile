# Copied from the boilerplate (see UPSTREAM.md). Local change: the image sets no
# EPICS_CA_ADDR_LIST default, so that RAS/mist2/.env is the only place for the
# Channel Access settings.
FROM epicsbase AS pvserver

RUN apt-get update && apt-get install -y  \
    libldap2-dev libsasl2-dev ldap-utils tox \
    lcov valgrind

WORKDIR /pvServer
ADD ./submodules/React-Automation-Studio/pvServer /pvServer

RUN --mount=type=cache,target=/opt/uv-cache/uv  \
    uv sync

ENV pvServerURL=http://127.0.0.1
ENV pvServerPort=5000
ENV pvServerNameSpace=pvServer
ENV VITE_EnableLogin=false
ENV VITE_DisableStandardLogin=false
ENV VITE_EnableActiveDirectoryLogin=false
ENV VITE_EnableGoogleLogin=false
ENV PYEPICS_LIBCA=/epics/base/lib/linux-x86_64/libca.so
ENV PATH="/epics/base/bin/linux-x86_64/:${PATH}"
VOLUME /pvServer/userAuthentication/users

CMD ["uv", "run", "pvServer.py"]
