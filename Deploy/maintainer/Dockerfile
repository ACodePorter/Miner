FROM --platform=linux/amd64 ubuntu:24.04

ENV AM_I_IN_DOCKER_CONTAINER=Yes

ENV DEBIAN_FRONTEND=noninteractive

RUN echo "dash dash/sh boolean false" | debconf-set-selections
RUN DEBIAN_FRONTEND=noninteractive dpkg-reconfigure dash

RUN apt-get update && \
        apt-get install -y ca-certificates gnupg curl apt-utils

RUN apt-get update && apt upgrade -y && \
        apt-get install -y wget locales sudo unzip git openssh-client curl jq libmagic-dev \
        tzdata

ENV TZ=America/Toronto
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && dpkg-reconfigure -f noninteractive tzdata

RUN useradd miner -G sudo,www-data,plugdev -s /bin/bash -m
RUN usermod -aG www-data miner
RUN echo miner:12qw | chpasswd

RUN locale-gen en_US.UTF-8

USER miner
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

COPY --chown=miner:miner release/ /miner_release/
RUN chmod a+x /miner_release/*.sh


RUN echo "export USER=$(whoami)" >> ~/.bashrc && \
        echo "export SHELL=/bin/bash" >>~/.bashrc
ENV HOME=/home/miner
COPY --chown=miner:miner release/bin/* $HOME/bin/
RUN chmod a+x $HOME/bin/*
WORKDIR $HOME
ENV PATH=$HOME/bin:$PATH
RUN cat $HOME/.bashrc
ENV CONDA_INS_DIR=$HOME/bin/conda
RUN echo "export PATH=$CONDA_INS_DIR/bin:\$PATH" >>~/.bashrc
ENV PATH=$CONDA_INS_DIR/bin:$PATH
RUN . $HOME/.bashrc

# Miniconda
COPY --chown=miner:miner .condarc $HOME/
RUN bash $HOME/bin/Miniconda3.sh -b -p $CONDA_INS_DIR && \
        conda init bash && \
        . $HOME/.bashrc && \
        . $CONDA_INS_DIR/etc/profile.d/conda.sh && \
        conda activate base
RUN rm -v $HOME/bin/Miniconda3.sh

RUN pip install uv && uv pip install --system /miner_release/Detonator /miner_release/DataMiner /miner_release/MinerWorkers /miner_release/Maintainer /miner_release/MarketBreadth

RUN rm -rfv /miner_release/Detonator /miner_release/DataMiner /miner_release/MinerWorkers /miner_release/Maintainer /miner_release/MarketBreadth

RUN mkdir -p $HOME/.miner
# COPY --chown=miner:miner miner.json $HOME/.miner/miner.json
RUN touch $HOME/.miner/miner.log

# Set git config for miner user and verify
ARG GIT_USER_NAME
ARG GIT_USER_EMAIL

RUN git config --global user.name "$GIT_USER_NAME" \
    && git config --global user.email "$GIT_USER_EMAIL"

# Build arguments for SSH key management
ARG GITHUB_TOKEN
# Copy SSH key management script
COPY --chown=miner:miner setup_ssh_keys.sh $HOME/bin/
RUN chmod +x $HOME/bin/setup_ssh_keys.sh

# Setup SSH keys (requires GITHUB_TOKEN environment variable)
RUN GITHUB_TOKEN="$GITHUB_TOKEN" $HOME/bin/setup_ssh_keys.sh

ENTRYPOINT /miner_release/docker_entry.sh
