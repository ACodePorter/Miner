ARG BASE_IMAGE=miner-base:latest
FROM ${BASE_IMAGE}

USER root
# Install Chromium instead of Google Chrome for ARM64 compatibility
RUN apt-get update && \
    apt-get install -y chromium-browser --no-install-recommends \
    libx11-6 libx11-xcb1 libxcomposite1 libxcursor1 libxdamage1 libxext6 \
    libxfixes3 libxi6 libxrandr2 libxrender1 libxtst6 libglib2.0-0 libnss3 \
    libasound2t64 x11-apps xvfb && \
    rm -rf /var/lib/apt/lists/* && apt-get clean

USER miner
COPY --chown=miner:miner release/ /miner_release/
COPY --chown=miner:miner docker_entry.sh /miner_release/
RUN chmod a+x /miner_release/*.sh

RUN chmod a+x $HOME/bin/*

RUN pip install uv && \
    uv pip install --system /miner_release/Detonator /miner_release/DataMiner /miner_release/BrowserScraper /miner_release/MinerWorkers && \
    rm -rfv /miner_release/Detonator /miner_release/DataMiner /miner_release/BrowserScraper /miner_release/MinerWorkers && \
    rm -rfv $HOME/.cache/uv && rm -rfv $HOME/.cache/pip

ENTRYPOINT xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" /miner_release/docker_entry.sh
