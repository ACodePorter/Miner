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

pip install $mydir/Detonator
pip install $mydir/Russell1000-Miner
pip install $mydir/MinerWorkers
pip install $mydir/MinerService

set +x
set +e
