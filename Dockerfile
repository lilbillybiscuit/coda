FROM ubuntu:22.04
LABEL authors="lilbillbiscuit"

ENV DEBIAN_FRONTEND=noninteractive

RUN ln -snf /usr/share/zoneinfo/UTC /etc/localtime && echo UTC > /etc/timezone
RUN apt-get update && apt-get install -y \
    curl \
    git \
    gnupg \
    jq \
    libgmp-dev \
    libssl-dev \
    pkg-config \
    software-properties-common \
    unzip \
    wget \
    zip \
    sudo \
    tree
RUN apt-get install python-is-python3 python3-pip -y


RUN useradd -m -s /bin/bash coda && \
    usermod -aG sudo coda && \
    echo "coda ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers


WORKDIR /workspace
RUN chown coda:coda /workspace
USER coda

# Command to keep container running
CMD ["tail", "-f", "/dev/null"]