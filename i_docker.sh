#!/bin/sh

# 部署最新代码到 Docker 中

docker compose -p miner start
docker exec -it --user 'miner' minerservice /minerdev/i_local.sh

docker compose -p miner stop
sleep 3
docker compose -p miner start
