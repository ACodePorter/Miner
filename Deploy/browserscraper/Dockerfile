FROM --platform=linux/amd64 ubuntu:24.04

ENV AM_I_IN_DOCKER_CONTAINER=Yes

ENV DEBIAN_FRONTEND=noninteractive

# Install base utilities first
RUN apt-get update && \
    apt-get install -y wget gnupg ca-certificates

# Now you can safely use wget and gpg
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Continue with the rest of your installs
RUN apt-get update && \
    apt-get install -y google-chrome-stable --no-install-recommends \
    locales sudo unzip git openssh-client curl jq libmagic-dev tzdata \
    libx11-6 libx11-xcb1 libxcomposite1 libxcursor1 libxdamage1 libxext6 \
    libxfixes3 libxi6 libxrandr2 libxrender1 libxtst6 libglib2.0-0 libnss3 \
    libasound2t64 x11-apps xvfb && \
    rm -rf /var/lib/apt/lists/* && apt-get clean

ENV TZ=America/Toronto
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && dpkg-reconfigure -f noninteractive tzdata

RUN useradd miner -G sudo,www-data,plugdev -s /bin/bash -m && \
    usermod -aG www-data miner && \
    echo miner:12qw | chpasswd && \
    locale-gen en_US.UTF-8

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
ENV PATH="$HOME/bin:$PATH"
RUN cat $HOME/.bashrc
ENV CONDA_INS_DIR=$HOME/bin/conda
RUN echo 'export PATH="$CONDA_INS_DIR"/bin:$PATH' >>~/.bashrc
ENV PATH="$CONDA_INS_DIR/bin:$PATH"
RUN . $HOME/.bashrc

# Miniconda
COPY --chown=miner:miner .condarc $HOME/
RUN bash $HOME/bin/Miniconda3.sh -b -p $CONDA_INS_DIR && \
        conda init bash && \
        . $HOME/.bashrc && \
        . $CONDA_INS_DIR/etc/profile.d/conda.sh && \
        conda activate base
RUN rm -v $HOME/bin/Miniconda3.sh

RUN pip install uv && \
    uv pip install --system /miner_release/Detonator /miner_release/DataMiner /miner_release/BrowserScraper /miner_release/MinerWorkers && \
    rm -rfv /miner_release/Detonator /miner_release/DataMiner /miner_release/BrowserScraper /miner_release/MinerWorkers && \
    rm -rfv $HOME/.cache/uv/http*

RUN mkdir -p $HOME/.miner
# COPY --chown=miner:miner miner.json $HOME/.miner/miner.json
RUN touch $HOME/.miner/miner.log

RUN mkdir $HOME/.ssh && \
        ssh-keyscan -H github.com >> $HOME/.ssh/known_hosts
#         ssh-keyscan -H  -p 29418 github.com >> $HOME/.ssh/known_hosts

# RUN ssh-keygen -q -t rsa -N '' -f $HOME/.ssh/id_rsa <<<y 
RUN ssh-keygen -t rsa -b 4096 -f $HOME/.ssh/id_rsa -N ""


# COPY --chown=miner:miner .ssh/config $HOME/.ssh/

ENTRYPOINT xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" /miner_release/docker_entry.sh
