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

cd $MY_DIR

wget -c https://repo.anaconda.com/miniconda/Miniconda3-py311_23.10.0-1-Linux-x86_64.sh -O $MY_DIR/miner/bin/Miniconda3.sh

MONGODB=$HOME/.miner/mongogo
mkdir -p $MONGODB

RELEASE_DIR=$MY_DIR/miner/release
rm -rf $RELEASE_DIR
mkdir -p $RELEASE_DIR

function cleanup() {
    rm -rf $RELEASE_DIR
}

java_version=$($JAVA_HOME/bin/java -version 2>&1 | awk -F '"' '/version/ {print $2}')
major_version=$(echo "$java_version" | awk -F '.' '{print $1}')

if [ "$major_version" -ge 17 ]; then
    echo ""
else
    echo ""
fi

cp -av $MY_DIR/../Detonator $RELEASE_DIR/
cp -av $MY_DIR/../Russell1000-Miner $RELEASE_DIR/
cp -av $MY_DIR/../MinerWorkers $RELEASE_DIR/
cp -av $MY_DIR/../MinerService $RELEASE_DIR/
cp -av $MY_DIR/miner/docker_entry.sh $RELEASE_DIR/

docker compose --project-name miner up --build -d

echo "Cleaning up ..."
rm -rf $RELEASE_DIR
cd $MY_PWD
set +x
set +e
