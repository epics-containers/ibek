# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
ARG PYTHON_VERSION=3.13
FROM ghcr.io/diamondlightsource/ubuntu-devcontainer:noble AS developer

# Add any system dependencies for the developer/build environment here
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    graphviz \
    && apt-get dist-clean
