#!/bin/sh

set -x
set -e

echo "Let's go ..."

MY_PWD=$PWD
MY_DIR=$(realpath $(dirname $0))

catch_user_signal() {
    cleanup
    cd $MY_PWD
    kill -KILL "$pid" 2>/dev/null
}

trap catcher_user_signal SIGTERM
trap catcher_user_signal SIGKILL
trap catcher_user_signal SIGQUIT
trap catcher_user_signal INT

usage() {
    echo "Usage: $0 <tushare_key> <runtime_env[PROD|TEST|DEV]> [miner_data_dir]"
    exit 1
}

if [ -n "$1" ]; then
    export TUSHARE_KEY=$1
else
    usage
    exit 1
fi

if [ -n "$2" ]; then
    export RUNTIME_ENV=$2
else
    usage
    exit 1
fi

mkdir -p $HOME/.miner/mongogo

export MINER_DATA=$HOME/.miner/data
if [ -n "$3" ];then
    export MINER_DATA=$2
fi

echo $TUSHARE_KEY
echo $MINER_DATA
mkdir -p $MINER_DATA

export MONGO_INITDB_ROOT_USERNAME=root
export MONGO_INITDB_ROOT_PASSWORD=12qw
if [ -n "$3" ]; then
    export MONGO_INITDB_ROOT_USERNAME=$3
fi
if [ -n "$4" ]; then
    export MONGO_INITDB_ROOT_PASSWORD=$4
fi

cd $MY_DIR

mkdir -p $MY_DIR/miner/bin/
wget -d -c https://repo.anaconda.com/miniconda/Miniconda3-py312_24.11.1-0-Linux-x86_64.sh -O $MY_DIR/miner/bin/Miniconda3.sh

RELEASE_DIR=$MY_DIR/miner/release
rm -rf $RELEASE_DIR
mkdir -p $RELEASE_DIR

function cleanup() {
    echo "Cleaning up ..."
    rm -rf $RELEASE_DIR
    cd $MY_PWD
}

java_version=$($JAVA_HOME/bin/java -version 2>&1 | awk -F '"' '/version/ {print $2}')
major_version=$(echo "$java_version" | awk -F '.' '{print $1}')

if [ "$major_version" -ge 17 ]; then
    echo ""
else
    echo ""
fi

cp -av $MY_DIR/../Detonator $RELEASE_DIR/
cp -av $MY_DIR/../DataMiner $RELEASE_DIR/
cp -av $MY_DIR/../MarketBreadth $RELEASE_DIR/
cp -av $MY_DIR/../MinerWorkers $RELEASE_DIR/
cp -av $MY_DIR/../MinerService $RELEASE_DIR/
cp -av $MY_DIR/../MinerService/run_service_as_prod_uds.sh $RELEASE_DIR/
cp -av $MY_DIR/miner/run_socks5_proxy.sh $RELEASE_DIR/
cp -av $MY_DIR/miner/docker_entry.sh $RELEASE_DIR/

docker -D compose --project-name miner up --build -d

cleanup

set +x
set +e
