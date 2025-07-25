ARG BASE_IMAGE
FROM ${BASE_IMAGE}

COPY --chown=miner:miner release/ /miner_release/
COPY --chown=miner:miner docker_entry.sh /miner_release/
RUN chmod a+x /miner_release/*.sh

USER miner

RUN uv pip install --system /miner_release/MinerTrader && \
        rm -rfv /miner_release/MinerTrader && \
        rm -rfv $HOME/.cache/uv && rm -rfv $HOME/.cache/pip


ENTRYPOINT /miner_release/docker_entry.sh
