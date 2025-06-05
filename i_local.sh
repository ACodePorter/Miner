#!/bin/sh

set -x
set -e

mydir=$(realpath $(dirname $0))

if [ -f "/.dockerenv" ];then
    echo "Running in docker"
else
    CONDA_INSTALL_DIR=$(dirname $(dirname $(which conda)))
    . $CONDA_INSTALL_DIR/etc/profile.d/conda.sh
    conda activate miner
    echo "Current Python Env:" $CONDA_DEFAULT_ENV
    mkdir -pv $HOME/.miner
    cp $mydir/Deploy/miner/miner.json $HOME/.miner/
fi


find "$mydir" -name requirements.txt -exec python -m pip install -q -U -r {} \;

pip install -q $mydir/Detonator
pip install -q $mydir/DataMiner
pip install -q $mydir/MarketBreadth
pip install -q $mydir/MinerWorkers
pip install -q $mydir/MinerService

set +x
set +e
