FROM --platform=linux/amd64 ubuntu:24.04

ENV AM_I_IN_DOCKER_CONTAINER=Yes

ENV DEBIAN_FRONTEND=noninteractive

RUN echo "dash dash/sh boolean false" | debconf-set-selections
RUN DEBIAN_FRONTEND=noninteractive dpkg-reconfigure dash

RUN apt-get update && \
        apt-get install -y ca-certificates gnupg curl apt-utils

RUN apt-get update && apt upgrade -y && \
        apt-get install -y wget locales sudo nginx unzip git openssh-client curl jq libmagic-dev openssh-client \
        tzdata

ENV TZ=America/Toronto
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && dpkg-reconfigure -f noninteractive tzdata

COPY --chown=root:root nginx.conf /etc/nginx/nginx.conf

RUN useradd miner -G sudo,www-data,plugdev -s /bin/bash -m
RUN usermod -aG www-data miner
RUN echo miner:12qw | chpasswd

RUN mkdir -p -m 775 /data/db && \
        chown miner:miner /data/db

EXPOSE 80 27017 2222 6666 8001

RUN locale-gen en_US.UTF-8

USER miner
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

COPY --chown=miner:miner release/ /miner_release/
RUN chmod a+x /miner_release/*.sh
# RUN chmod a+x /miner_release/run_service_as_prod_uds.sh


RUN echo "export USER=$(whoami)" >> ~/.bashrc && \
        echo "export SHELL=/bin/bash" >>~/.bashrc
ENV HOME=/home/miner
COPY --chown=miner:miner bin/* $HOME/bin/
WORKDIR $HOME
ENV PATH=$HOME/bin:$PATH
RUN cat $HOME/.bashrc
ENV CONDA_INS_DIR=$HOME/bin/conda
RUN echo 'export PATH="$CONDA_INS_DIR"/bin:$PATH' >>~/.bashrc
ENV PATH="$CONDA_INS_DIR"/bin:$PATH
RUN . $HOME/.bashrc

# Miniconda
COPY --chown=miner:miner .condarc $HOME/
RUN bash $HOME/bin/Miniconda3.sh -b -p $CONDA_INS_DIR && \
        conda init bash && \
        . $HOME/.bashrc && \
        . $CONDA_INS_DIR/etc/profile.d/conda.sh && \
        conda activate base
        # pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
RUN rm -rfv $HOME/bin/Miniconda3.sh
RUN pip install uv
RUN uv pip install --system /miner_release/Detonator
RUN uv pip install --system /miner_release/DataMiner
RUN uv pip install --system /miner_release/MarketBreadth
RUN uv pip install --system /miner_release/MinerWorkers
RUN uv pip install --system /miner_release/BrowserScraper
RUN uv pip install --system /miner_release/MinerService


RUN mkdir -p $HOME/.miner
COPY --chown=miner:miner miner.json $HOME/.miner/miner.json
RUN touch $HOME/.miner/miner.log

RUN mkdir $HOME/.ssh && \
        ssh-keyscan -H github.com >> $HOME/.ssh/known_hosts
#         ssh-keyscan -H  -p 29418 github.com >> $HOME/.ssh/known_hosts

# RUN ssh-keygen -q -t rsa -N '' -f $HOME/.ssh/id_rsa <<<y 
RUN ssh-keygen -t rsa -b 4096 -f $HOME/.ssh/id_rsa -N ""


COPY --chown=miner:miner .ssh/config $HOME/.ssh/

ENTRYPOINT /miner_release/docker_entry.sh
