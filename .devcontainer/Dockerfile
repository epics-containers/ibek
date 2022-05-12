# ideas from https://www.docker.com/blog/containerized-python-development-part-1/

# This file is for use as a .vscode devcontainer as well as a runtime 
# container. The devcontainer should be rootful and use podman or docker 
# with user namespaces.

ARG BASE="mcr.microsoft.com/vscode/devcontainers/python:0-3.10-bullseye"
FROM ${BASE} as base

# use root to pin where the packages will install
USER root
ENV PATH=/root/.local/bin:$PATH

# things to make pyQt5 work
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive && \
    apt-get install -y --no-install-recommends \
    libqt5gui5 libxcb-xinerama0 && \
    rm -rf /var/lib/apt/lists/*
    
ENV XDG_RUNTIME_DIR=/tmp/runtime-vscode

FROM base as developer

WORKDIR /workspace
COPY . .

# install runtime from DIST if there is one
RUN mkdir -p /root/.local && \
    test -d dist && \
    requirements=$(test -f requirements.txt && echo -r requirements.txt) \
    pip install --user $requirements dist/*.whl || :

FROM base as runtime
COPY --from=developer /root/.local /root/.local

ENTRYPOINT ["ibek"]
