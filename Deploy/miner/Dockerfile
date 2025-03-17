FROM --platform=linux/amd64 ubuntu:24.04

ENV TZ=America/Toronto
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

ENV AM_I_IN_DOCKER_CONTAINER=Yes

ENV DEBIAN_FRONTEND=noninteractive

RUN echo "dash dash/sh boolean false" | debconf-set-selections
RUN DEBIAN_FRONTEND=noninteractive dpkg-reconfigure dash

RUN apt-get update && \
        apt-get install -y ca-certificates gnupg curl apt-utils
# RUN echo 'deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ focal main restricted universe multiverse' > /etc/apt/sources.list && \
#         echo 'deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ focal-updates main restricted universe multiverse' >> /etc/apt/sources.list && \
#         echo 'deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ focal-backports main restricted universe multiverse' >> /etc/apt/sources.list && \
#         echo 'deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ focal-security main restricted universe multiverse' >> /etc/apt/sources.list

RUN curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
RUN echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-8.0.list
RUN apt-get update && apt upgrade -y && \
        apt-get install -y wget locales sudo nginx mongodb-org unzip git openssh-client curl jq libmagic-dev openssh-client
# RUN systemctl daemon-reload
# RUN systemctl start mongod

COPY --chown=root:root nginx.conf /etc/nginx/nginx.conf

RUN useradd miner -G sudo,www-data,plugdev,mongodb -s /bin/bash -m
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
        # rm -rfv $HOME/bin/Miniconda3*

RUN pip install /miner_release/Detonator
RUN pip install /miner_release/DataMiner
RUN pip install /miner_release/MarketBreadth
RUN pip install /miner_release/MinerWorkers
RUN pip install /miner_release/MinerService

RUN mkdir -p $HOME/.miner
COPY --chown=miner:miner miner.json $HOME/.miner/miner.json
RUN touch $HOME/.miner/miner.log

RUN mkdir $HOME/.ssh && \
        ssh-keyscan -H github.com >> $HOME/.ssh/known_hosts \
        ssh-keyscan -H 54.153.40.36 >> $HOME/.ssh/known_hosts
#         ssh-keyscan -H  -p 29418 github.com >> $HOME/.ssh/known_hosts

# RUN ssh-keygen -q -t rsa -N '' -f $HOME/.ssh/id_rsa <<<y 
RUN ssh-keygen -t rsa -b 4096 -f $HOME/.ssh/id_rsa -N ""


COPY --chown=miner:miner .ssh/config $HOME/.ssh/

# Install jdk
# RUN tar xvf $HOME/bin/jdk-17.0.9_linux-x64_bin.tar.gz -C $HOME/bin
# ENV JAVA_HOME="$HOME/bin/jdk-17.0.9"
# ENV PATH="$JAVA_HOME/bin:$PATH"
# RUN rm -rfv $HOME/bin/jdk-17.0.9_linux-x64_bin.tar.gz


# Install nodejs
# RUN tar xzvf $HOME/bin/node-v16.20.2-linux-x64.tar.gz -C $HOME/bin
# ENV PATH="$HOME/bin/node-v16.20.2-linux-x64/bin:$PATH"

ENTRYPOINT /miner_release/docker_entry.sh
# ENTRYPOINT bash
