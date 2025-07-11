#!/bin/sh

# 部署最新代码到 Docker 中
set -x
set -e
docker compose -p miner start
docker exec -it --user 'miner' minerservice /minerdev/i_local.sh

docker exec -it --user 'miner' minerservice /minerdev/restart_service.sh

set +e
set +x
echo "$basename $0 done"
