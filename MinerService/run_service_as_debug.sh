#!/usr/bin/env bash

my_dir="$(realpath "$(dirname "$0")")"
cur_dur=$(pwd)
cd "$my_dir" || exit

export PYTHONPATH="$my_dir:$my_dir/../DataMiner:$my_dir/../Detonator:$my_dir/../MarketBreadth:$my_dir/../MinerWorkers:$PYTHONPATH"


uvicorn --host 127.0.0.1 --port 8888 --log-level debug \
        --reload \
        --reload-dir "$my_dir" \
        --reload-dir "$my_dir/../DataMiner" \
        --reload-dir "$my_dir/../Detonator" \
        --reload-dir "$my_dir/../MarketBreadth" \
        --reload-dir "$my_dir/../MinerWorkers" \
        minerservice.main:app


cd "$cur_dur" || exit