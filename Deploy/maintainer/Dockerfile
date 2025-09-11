ARG BASE_IMAGE=miner-base:latest
FROM --platform=linux/amd64 ${BASE_IMAGE} AS base

USER miner

COPY --chown=miner:miner release/ /miner_release/
COPY --chown=miner:miner docker_entry.sh /miner_release/
RUN chmod a+x /miner_release/*.sh



RUN uv pip install --system /miner_release/Detonator /miner_release/DataMiner /miner_release/MinerWorkers /miner_release/Maintainer /miner_release/MarketBreadth && \
    rm -rfv /miner_release/Detonator /miner_release/DataMiner /miner_release/MinerWorkers /miner_release/Maintainer /miner_release/MarketBreadth && \
    rm -rfv $HOME/.cache/uv && rm -rfv $HOME/.cache/pip

# pass runtime env to the script
ARG RUNTIME_ENV
# Set git config for miner user and verify
ARG GIT_USER_NAME
ARG GIT_USER_EMAIL

# Build arguments for SSH key management
ARG GITHUB_TOKEN
# Copy SSH key management script
COPY --chown=miner:miner setup_ssh_keys.sh $HOME/bin/
RUN chmod +x $HOME/bin/setup_ssh_keys.sh && \
    git config --global user.name "$GIT_USER_NAME" \
    && git config --global user.email "$GIT_USER_EMAIL"

# Setup SSH keys (requires GITHUB_TOKEN environment variable)
RUN GITHUB_TOKEN="$GITHUB_TOKEN" $HOME/bin/setup_ssh_keys.sh && \
    rm -rfv $HOME/bin/setup_ssh_keys.sh

ENTRYPOINT /miner_release/docker_entry.sh
