#!/bin/sh

# 部署最新代码到 Docker 中
set -x
set -e
docker compose -p miner start
docker exec -it --user 'miner' minerservice /minerdev/i_local.sh

docker exec -it --user 'miner' minerservice killall uvicorn
docker exec -dt --user 'miner' minerservice /miner_release/run_service_as_prod_uds.sh 2>&1 &

set +e
set +x
echo "$basename $0 done"
