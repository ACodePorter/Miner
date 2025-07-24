ARG BASE_IMAGE
FROM ${BASE_IMAGE}

USER root
RUN apt update && apt install -y nginx && rm -rf /var/lib/apt/lists/* && apt-get clean
COPY --chown=root:root nginx.conf /etc/nginx/nginx.conf

# EXPOSE 80 27017 2222 6666 8001

USER miner

COPY --chown=miner:miner release/ /miner_release/
COPY --chown=miner:miner docker_entry.sh /miner_release/
RUN chmod a+x /miner_release/*.sh


RUN uv pip install --system /miner_release/Detonator /miner_release/DataMiner /miner_release/MarketBreadth /miner_release/MinerWorkers /miner_release/BrowserScraper /miner_release/MinerService && \
    rm -rfv /miner_release/Detonator /miner_release/DataMiner /miner_release/MarketBreadth /miner_release/MinerWorkers /miner_release/BrowserScraper /miner_release/MinerService && \
    rm -rfv $HOME/.cache/uv && rm -rfv $HOME/.cache/pip

COPY --chown=miner:miner miner.json $HOME/.miner/miner.json

USER root

ENTRYPOINT /miner_release/docker_entry.sh
