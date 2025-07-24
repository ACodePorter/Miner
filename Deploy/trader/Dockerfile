ARG BASE_IMAGE
FROM ${BASE_IMAGE}

COPY --chown=miner:miner release/ /miner_release/
COPY --chown=miner:miner docker_entry.sh /miner_release/
RUN chmod a+x /miner_release/*.sh

USER miner

RUN uv pip install --system /miner_release/Detonator /miner_release/DataMiner /miner_release/MinerWorkers /miner_release/Maintainer /miner_release/MarketBreadth && \
        rm -rfv /miner_release/Detonator /miner_release/DataMiner /miner_release/MinerWorkers /miner_release/Maintainer /miner_release/MarketBreadth && \
        rm -rfv $HOME/.cache/uv && rm -rfv $HOME/.cache/pip


ENTRYPOINT /miner_release/docker_entry.sh
